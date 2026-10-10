"""REST API over the dispatch service (PRD 7, 10)."""
from __future__ import annotations

import argparse
import fnmatch
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from cognitive_mirror import SCHEMA_VERSION, __version__
from cognitive_mirror.catalog import TOOLS
from cognitive_mirror.config import Settings, get_settings, load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.schemas import all_schemas
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store, input_hash, new_request_id

STATUS_FOR_CODE = {"invalid_input": 422, "unknown_tool": 404, "unauthorized": 401,
                   "forbidden": 403, "not_found": 404, "conflict": 409, "internal_error": 500}

UI_HTML = Path(__file__).resolve().parent / "ui.html"
APPROVAL_RISKS = ("low", "medium", "high", "critical")
APPROVAL_STATES = ("pending", "approved", "rejected")
APPROVAL_DECISIONS = ("approved", "rejected")


def _role_from_headers(settings: Settings, x_api_key: str | None,
                       authorization: str | None) -> str | None:
    key = (x_api_key or "").strip()
    if not key and authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            key = parts[1].strip()
    if not key:
        return None if settings.require_auth else settings.stdio_role
    return settings.role_for_key(key or None)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = Store(settings.db_path, settings.retention_days, settings.shared_context_ttl_minutes)
    lexicon = load_lexicon(str(settings.jev_config_path) if settings.jev_config_path else None)
    service = Service(settings, store, lexicon)
    app = FastAPI(title="CognitiveMirror-Jev-MCP", version=__version__)
    app.state.settings = settings
    app.state.service = service

    def _deny_host(request: Request) -> JSONResponse | None:
        if settings.allowed_hosts:
            host = (request.headers.get("host") or "").strip()
            if not any(fnmatch.fnmatch(host, pat) for pat in settings.allowed_hosts):
                return JSONResponse({"error": {"code": "forbidden",
                                               "message": "Host not allowed"}}, status_code=403)
        return None

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui", status_code=307)

    @app.get("/ui", include_in_schema=False)
    def ui() -> FileResponse:
        return FileResponse(UI_HTML, media_type="text/html")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "schema_version": SCHEMA_VERSION,
                "deployment_mode": settings.deployment_mode,
                "tools": sorted(TOOLS), "core_tools": sorted(
                    [n for n, s in TOOLS.items() if s.core])}

    @app.get("/v1/schemas")
    def schemas() -> dict:
        return {"schema_version": SCHEMA_VERSION, "tools": all_schemas()}

    @app.get("/v1/schemas/{tool}")
    def schema_one(tool: str) -> JSONResponse:
        schemas_map = all_schemas()
        if tool not in schemas_map:
            return JSONResponse({"error": {"code": "unknown_tool", "message": tool}}, status_code=404)
        return JSONResponse(schemas_map[tool])

    @app.post("/v1/tools/{tool}")
    async def call_tool(tool: str, request: Request,
                        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
                        authorization: str | None = Header(default=None)) -> JSONResponse:
        denied = _deny_host(request)
        if denied is not None:
            return denied
        role = _role_from_headers(settings, x_api_key, authorization)
        if role is None:
            return JSONResponse({"error": {"code": "unauthorized",
                                           "message": "Missing or invalid API key"}},
                                status_code=401)
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - malformed body falls back to {}
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        agent_id = request.headers.get("X-Agent-ID")
        out = service.call(tool, payload, role, agent_id)
        if "error" in out:
            return JSONResponse(out, status_code=STATUS_FOR_CODE[out["error"]["code"]])
        return JSONResponse(out)

    @app.post("/v1/approvals", status_code=201)
    async def approval_create(request: Request,
                              x_api_key: str | None = Header(default=None, alias="X-API-Key"),
                              authorization: str | None = Header(default=None)) -> JSONResponse:
        denied = _deny_host(request)
        if denied is not None:
            return denied
        if _role_from_headers(settings, x_api_key, authorization) is None:
            return JSONResponse({"error": {"code": "unauthorized",
                                           "message": "Missing or invalid API key"}},
                                status_code=401)
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - malformed body falls back to {}
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        action = str(payload.get("planned_action") or "").strip()
        if not action:
            return JSONResponse({"error": {"code": "invalid_input",
                                           "message": "planned_action is required"}},
                                status_code=422)
        risk = str(payload.get("risk_level") or "medium")
        if risk not in APPROVAL_RISKS:
            return JSONResponse({"error": {"code": "invalid_input",
                                           "message": f"risk_level must be one of "
                                                      f"{list(APPROVAL_RISKS)}"}},
                                status_code=422)
        reasons = payload.get("reasons") or []
        item = store.approval_create(
            action, risk, str(payload.get("trace_id") or ""),
            [str(r) for r in reasons] if isinstance(reasons, list) else [],
            payload.get("safe_alternative"))
        return JSONResponse(item, status_code=201)

    @app.get("/v1/approvals")
    def approval_list(request: Request, status: str | None = None,
                      x_api_key: str | None = Header(default=None, alias="X-API-Key"),
                      authorization: str | None = Header(default=None)) -> JSONResponse:
        denied = _deny_host(request)
        if denied is not None:
            return denied
        if _role_from_headers(settings, x_api_key, authorization) is None:
            return JSONResponse({"error": {"code": "unauthorized",
                                           "message": "Missing or invalid API key"}},
                                status_code=401)
        if status is not None and status not in APPROVAL_STATES:
            return JSONResponse({"error": {"code": "invalid_input",
                                           "message": f"status must be one of "
                                                      f"{list(APPROVAL_STATES)}"}},
                                status_code=422)
        return JSONResponse({"items": store.approval_list(status)})

    @app.post("/v1/approvals/{approval_id}/decision")
    async def approval_decide(approval_id: str, request: Request,
                              x_api_key: str | None = Header(default=None, alias="X-API-Key"),
                              authorization: str | None = Header(default=None)) -> JSONResponse:
        denied = _deny_host(request)
        if denied is not None:
            return denied
        role = _role_from_headers(settings, x_api_key, authorization)
        if role is None:
            return JSONResponse({"error": {"code": "unauthorized",
                                           "message": "Missing or invalid API key"}},
                                status_code=401)
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - malformed body falls back to {}
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        decision = str(payload.get("decision") or "")
        if decision not in APPROVAL_DECISIONS:
            return JSONResponse({"error": {"code": "invalid_input",
                                           "message": f"decision must be one of "
                                                      f"{list(APPROVAL_DECISIONS)}"}},
                                status_code=422)
        try:
            item = store.approval_decide(approval_id, decision,
                                         str(payload.get("reason") or ""), role)
        except ValueError as exc:
            return JSONResponse({"error": {"code": "conflict", "message": str(exc)}},
                                status_code=409)
        if item is None:
            return JSONResponse({"error": {"code": "not_found",
                                           "message": f"Unknown approval {approval_id!r}"}},
                                status_code=404)
        store.audit_write({
            "request_id": new_request_id(), "trace_id": item["trace_id"] or approval_id,
            "session_id": None, "tool": "approval_decision", "tool_version": "1.0.0",
            "caller_role": role, "agent_id": request.headers.get("X-Agent-ID"),
            "status": "ok", "error_code": None, "engine_mode": "deterministic",
            "model_version": "cm-rules-1.0", "input_hash": input_hash({"id": approval_id}),
            "input_redacted": {"id": approval_id, "decision": decision},
            "output_redacted": item, "policy_decision": None,
            "latency_ms": 0.0, "created_at": datetime.now(timezone.utc).isoformat()})
        return JSONResponse(item)

    return app


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - entrypoint
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    import uvicorn
    uvicorn.run(create_app(load_settings()), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
