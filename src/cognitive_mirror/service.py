"""Dispatch layer: auth, validation, memory resolution, engines, audit (PRD 7, 9)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from cognitive_mirror import RULES_MODEL_VERSION, SCHEMA_VERSION
from cognitive_mirror.catalog import TOOLS
from cognitive_mirror.config import Settings
from cognitive_mirror.engine import ResolvedMemory
from cognitive_mirror.engine.actions import recommend_next_action
from cognitive_mirror.engine.decision import frame_decision
from cognitive_mirror.engine.guardrails import check_guardrails, load_policy, policy_names, redact
from cognitive_mirror.engine.impact import assess_business_impact
from cognitive_mirror.engine.intent import mirror_user_intent
from cognitive_mirror.engine.jev import build_jev_profile
from cognitive_mirror.engine.lexicons import Lexicon
from cognitive_mirror.engine.text import truncate
from cognitive_mirror.jev_live import apply_jev_live
from cognitive_mirror.llm import enrich
from cognitive_mirror.models import Epistemics
from cognitive_mirror.schemas import all_schemas
from cognitive_mirror.store import Store, input_hash, new_request_id, now_ms

ERROR_HINTS = {
    "invalid_input": "Fix the listed fields and retry; schemas at get_tool_schemas",
    "unknown_tool": "List tools with get_tool_schemas",
    "unauthorized": "Provide a valid API key for your role",
    "forbidden": "Your role cannot call this tool; ask an admin",
    "not_found": "The referenced request_id or memory ref does not exist",
    "internal_error": "Retry once; contact support with the request_id if it persists",
}


def _error(request_id: str, trace_id: str, tool: str, code: str, message: str,
           details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"request_id": request_id, "trace_id": trace_id, "tool": tool,
            "error": {"code": code, "message": message,
                      "recoverable": code in ("invalid_input", "unauthorized", "not_found"),
                      "hint": ERROR_HINTS[code], "details": details or []}}


def _redacted(payload: dict[str, Any]) -> dict[str, Any]:
    from cognitive_mirror.engine.guardrails import redact_obj
    return redact_obj(payload)  # type: ignore[return-value]


class Service:
    def __init__(self, settings: Settings, store: Store, lexicon: Lexicon) -> None:
        self.settings = settings
        self.store = store
        self.lexicon = lexicon

    # ---------------------------------------------------------- public entry
    def call(self, tool: str, payload: dict[str, Any] | None, role: str | None,
             agent_id: str | None = None) -> dict[str, Any]:
        start = now_ms()
        payload = dict(payload or {})
        request_id = new_request_id()
        trace_id = str(payload.get("trace_id") or f"tr_{uuid.uuid4().hex[:12]}")
        payload["trace_id"] = trace_id
        session_id = payload.get("session_id")

        if role is None:
            err = _error(request_id, trace_id, tool, "unauthorized", "Missing API credentials")
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "unauthorized", payload, None, None, start)
            return err
        spec = TOOLS.get(tool)
        if spec is None:
            err = _error(request_id, trace_id, tool, "unknown_tool", f"Unknown tool {tool!r}")
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "unknown_tool", payload, None, None, start)
            return err
        if role not in spec.roles:
            err = _error(request_id, trace_id, tool, "forbidden",
                         f"Role {role!r} cannot call {tool}")
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "forbidden", payload, None, None, start)
            return err
        try:
            parsed = spec.input_model(**payload)
        except Exception as exc:  # noqa: BLE001 - pydantic ValidationError
            details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")}
                       for e in getattr(exc, "errors", list)()]
            err = _error(request_id, trace_id, tool, "invalid_input",
                         f"Invalid input for {tool}", details)
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "invalid_input", payload, None, None, start)
            return err
        self._current_role = role
        try:
            result, confidence, epistemics, evidence, warnings, policy = self._run(tool, parsed)
        except PermissionError as exc:
            err = _error(request_id, trace_id, tool, "forbidden", str(exc))
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "forbidden", payload, None, None, start)
            return err
        except KeyError as exc:
            err = _error(request_id, trace_id, tool, "not_found", str(exc))
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "not_found", payload, None, None, start)
            return err
        except Exception as exc:  # noqa: BLE001 - defensive; pragma: no cover
            err = _error(request_id, trace_id, tool, "internal_error", f"Internal error: {exc}")
            self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                        "error", "internal_error", payload, None, None, start)
            return err

        enriched = tool == "build_jev_profile" and apply_jev_live(
            parsed, result, evidence, warnings, self.settings)
        llm_enriched, llm_warnings = enrich(tool, result, self.settings)
        enriched = enriched or llm_enriched
        warnings = [*warnings, *llm_warnings]
        latency = now_ms() - start
        envelope = {
            "request_id": request_id, "trace_id": trace_id, "session_id": session_id,
            "tool": tool, "tool_version": spec.version, "schema_version": SCHEMA_VERSION,
            "engine": {"mode": "hybrid" if enriched else "deterministic",
                       "model_version": RULES_MODEL_VERSION, "enriched": enriched},
            "result": result, "epistemics": epistemics.model_dump(),
            "confidence": confidence, "evidence": evidence, "warnings": warnings,
            "latency_ms": round(latency, 2),
        }
        self._audit(request_id, trace_id, session_id, tool, role, agent_id,
                    "ok", None, payload, result, policy, start, latency)
        if session_id:
            self.store.shared_publish(session_id, {
                "tool": tool, "request_id": request_id, "trace_id": trace_id,
                "caller_role": role, "agent_id": agent_id,
                "created_at": datetime.now(timezone.utc).isoformat(), "result": result})
        return envelope

    # ---------------------------------------------------------- runners
    def _run(self, tool: str, parsed: Any) -> tuple[dict, float, Epistemics,
                                                   list[dict], list[str], dict | None]:
        if tool == "mirror_user_intent":
            mem = self._resolve(parsed.available_memory_refs, parsed.subject_id)
            out = mirror_user_intent(parsed, mem, self.lexicon)
            return out.result, out.confidence, out.epistemics, out.evidence, out.warnings, None
        if tool == "build_jev_profile":
            mem = self._resolve(parsed.memory_refs, parsed.subject.id)
            out = build_jev_profile(parsed, mem, self.lexicon)
            if parsed.persist:
                if not parsed.consent:
                    out.warnings.append("persist=true needs consent=true; profile not stored")
                else:
                    ref, _exp = self.store.memory_store(
                        parsed.subject.id or "default", json.dumps(out.result, default=str),
                        "profile", [], None, ["jev_profile"])
                    out.result = dict(out.result, profile_ref=ref)
            return out.result, out.confidence, out.epistemics, out.evidence, out.warnings, None
        if tool == "recommend_next_action":
            out = recommend_next_action(parsed, self.lexicon)
            return out.result, out.confidence, out.epistemics, out.evidence, out.warnings, None
        if tool == "frame_decision":
            out = frame_decision(parsed, self.lexicon)
            return out.result, out.confidence, out.epistemics, out.evidence, out.warnings, None
        if tool == "assess_business_impact":
            out = assess_business_impact(parsed, self.lexicon)
            return out.result, out.confidence, out.epistemics, out.evidence, out.warnings, None
        if tool == "check_guardrails":
            out = check_guardrails(parsed, self.settings.policy_profile)
            return out.result, out.confidence, out.epistemics, out.evidence, out.warnings, \
                {"profile": out.policy_decision["profile"] if out.policy_decision else None,
                 "allowed": out.result["allowed"]}
        if tool == "memory_store":
            return self._memory_store(parsed)
        if tool == "memory_recall":
            return self._memory_recall(parsed)
        if tool == "memory_forget":
            if parsed.ref is None and self._role_of(parsed) != "admin":
                raise PermissionError("Forgetting all memory requires admin role")
            deleted = self.store.memory_forget(parsed.subject_id, parsed.ref)
            result = {"deleted": deleted, "subject_id": parsed.subject_id}
            return result, 1.0, Epistemics(), [], [], None
        if tool == "get_shared_context":
            entries = self.store.shared_get(parsed.session_id)
            latest: dict[str, dict[str, Any]] = {}
            for e in entries:
                latest[e["tool"]] = e["result"]
            result = {"session_id": parsed.session_id,
                      "entries": [{"tool": e["tool"], "request_id": e["request_id"],
                                   "trace_id": e["trace_id"], "caller_role": e["caller_role"],
                                   "agent_id": e["agent_id"], "created_at": e["created_at"],
                                   "result": e["result"]} for e in entries],
                      "latest_by_tool": latest}
            return result, 1.0, Epistemics(), [], [], None
        if tool == "record_feedback":
            found = self.store.audit_has(parsed.request_id)
            fid = self.store.feedback_write(parsed.request_id, parsed.rating,
                                            parsed.useful, parsed.outcome, parsed.comment)
            return {"recorded": True, "feedback_id": fid, "request_found": found}, 1.0, \
                Epistemics(), [], ([] if found else ["request_id not found in audit"]), None
        if tool == "get_tool_schemas":
            schemas = all_schemas()
            if parsed.tool:
                if parsed.tool not in schemas:
                    raise KeyError(f"Unknown tool {parsed.tool!r}")
                schemas = {parsed.tool: schemas[parsed.tool]}
            return {"schema_version": SCHEMA_VERSION, "tools": schemas}, 1.0, Epistemics(), [], [], None
        if tool == "get_audit_trail":
            records = self.store.audit_query(parsed.request_id, parsed.filter_trace_id,
                                             parsed.tool, parsed.limit)
            return {"records": records, "count": len(records)}, 1.0, Epistemics(), [], [], None
        if tool == "list_policy_profiles":
            profiles = {name: load_policy(name) for name in policy_names()}
            return {"active_profile": self.settings.policy_profile,
                    "profiles": profiles}, 1.0, Epistemics(), [], [], None
        raise KeyError(f"Unknown tool {tool!r}")  # pragma: no cover - guarded above

    def _role_of(self, _parsed: Any) -> str:
        return getattr(self, "_current_role", "agent")

    def _resolve(self, refs: list[str], subject_id: str | None) -> list[ResolvedMemory]:
        out: list[ResolvedMemory] = []
        for ref in refs:
            row = self.store.memory_get(ref, subject_id or "") if subject_id else None
            if row is None:
                # check existence under another subject
                with self.store._connect() as conn:
                    other = conn.execute("SELECT subject_id,expires_at FROM memories WHERE ref=?",
                                         (ref,)).fetchone()
                if other is None:
                    out.append(ResolvedMemory(ref, "missing", "", 0.0, None))
                else:
                    out.append(ResolvedMemory(ref, "out_of_scope", "", 0.0, None))
                continue
            from datetime import datetime
            expired = datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc)
            if expired:
                out.append(ResolvedMemory(ref, "expired", "", 0.0, None))
                continue
            created = datetime.fromisoformat(row["created_at"])
            age = (datetime.now(timezone.utc) - created).total_seconds() / 86400.0
            content = row["content"] if isinstance(row["content"], str) else str(row["content"])
            conf = 0.9 if age < 7 else (0.6 if age < 30 else 0.4)
            out.append(ResolvedMemory(ref, "resolved", truncate(content, 2000), conf, round(age, 2)))
        return out

    def _memory_store(self, parsed: Any) -> tuple[dict, float, Epistemics, list, list, None]:
        if not parsed.consent:
            result = {"stored": False, "memory_ref": None, "kind": parsed.kind,
                      "expires_at": None, "redactions": [], "reason": "consent=false"}
            return result, 1.0, Epistemics(
                assumptions=["Storage requires explicit consent"]), [], \
                ["Set consent=true to store memory"], None
        redacted, findings = redact(parsed.content)
        ref, expires = self.store.memory_store(parsed.subject_id, redacted, parsed.kind,
                                               [f.type for f in findings],
                                               parsed.ttl_days, parsed.tags)
        result = {"stored": True, "memory_ref": ref, "kind": parsed.kind,
                  "expires_at": expires, "redactions": [f.type for f in findings], "reason": None}
        return result, 1.0, Epistemics(facts=[f"Stored {parsed.kind} memory for {parsed.subject_id}"]), \
            [{"source": "content", "quote": truncate(redacted, 80)}], [], None

    def _memory_recall(self, parsed: Any) -> tuple[dict, float, Epistemics, list, list, None]:
        live, missing = self.store.memory_recall(parsed.subject_id, parsed.query,
                                                 parsed.refs, parsed.kind, parsed.limit)
        from datetime import datetime
        items = []
        for row in live:
            created = datetime.fromisoformat(row["created_at"])
            age = (datetime.now(timezone.utc) - created).total_seconds() / 86400.0
            conf = 0.9 if age < 7 else (0.6 if age < 30 else 0.4)
            q = parsed.query.lower().strip()
            rel = 0.9 if q and q in (row["content"] or "").lower() else (0.5 if q else 0.6)
            items.append({"ref": row["ref"], "kind": row["kind"], "content": row["content"],
                          "tags": json.loads(row["tags"]), "created_at": row["created_at"],
                          "expires_at": row["expires_at"], "age_days": round(age, 2),
                          "confidence": conf, "relevance": rel})
        coverage = round(sum(i["confidence"] for i in items) / len(items), 3) if items else 0.0
        note = "No items found" if not items else f"{len(items)} item(s); {len(missing)} missing ref(s)"
        return {"items": items, "missing_refs": missing,
                "coverage_confidence": coverage, "note": note}, coverage or 0.5, \
            Epistemics(), [], [], None

    def _audit(self, request_id: str, trace_id: str, session_id: str | None, tool: str,
               role: str | None, agent_id: str | None, status: str, error_code: str | None,
               payload: dict, result: dict | None, policy: dict | None,
               start: float, latency: float | None = None) -> None:
        spec = TOOLS.get(tool)
        try:
            self.store.audit_write({
                "request_id": request_id, "trace_id": trace_id, "session_id": session_id,
                "tool": tool, "tool_version": spec.version if spec else "0.0.0",
                "caller_role": role or "unknown", "agent_id": agent_id, "status": status,
                "error_code": error_code, "engine_mode": "deterministic",
                "model_version": RULES_MODEL_VERSION, "input_hash": input_hash(payload),
                "input_redacted": _redacted(payload), "output_redacted": result,
                "policy_decision": policy,
                "latency_ms": round((latency if latency is not None else now_ms() - start), 2),
                "created_at": datetime.now(timezone.utc).isoformat()})
        except Exception:  # noqa: BLE001, S110 - audit must never break; pragma: no cover
            pass

    def call_as(self, tool: str, payload: dict[str, Any] | None, role: str) -> dict[str, Any]:
        """Role-aware entry used by memory_forget admin gate."""
        self._current_role = role
        try:
            if tool == "memory_forget" and (payload or {}).get("ref") is None and role != "admin":
                request_id = new_request_id()
                trace_id = str((payload or {}).get("trace_id") or f"tr_{uuid.uuid4().hex[:12]}")
                err = _error(request_id, trace_id, tool, "forbidden",
                             "Forgetting all memory requires admin role")
                self._audit(request_id, trace_id, (payload or {}).get("session_id"), tool,
                            role, None, "error", "forbidden", dict(payload or {}), None, None,
                            now_ms())
                return err
            return self.call(tool, payload, role)
        finally:
            self._current_role = "agent"
