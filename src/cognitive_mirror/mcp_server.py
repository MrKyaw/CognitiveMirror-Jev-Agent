"""MCP server: stdio + streamable-http over the same dispatch service (MCP-001..008)."""
from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from cognitive_mirror.catalog import TOOLS
from cognitive_mirror.config import Settings, get_settings, load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store

mcp = FastMCP("cognitive-mirror-jev-mcp")
SERVICE: Service | None = None
ROLE = "agent"


def configure(settings: Settings | None = None) -> FastMCP:
    global SERVICE, ROLE
    settings = settings or get_settings()
    store = Store(settings.db_path, settings.retention_days, settings.shared_context_ttl_minutes,
                  settings.database_url)
    lexicon = load_lexicon(str(settings.jev_config_path) if settings.jev_config_path else None)
    SERVICE = Service(settings, store, lexicon)
    ROLE = settings.stdio_role
    return mcp


def _call(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    assert SERVICE is not None, "call configure() first"
    return SERVICE.call(tool, payload, ROLE)


@mcp.tool(name="mirror_user_intent", title="Mirror user intent",
          description=TOOLS["mirror_user_intent"].description)
def t_mirror(user_message: str, conversation_context: list[str] | None = None,
             available_memory_refs: list[str] | None = None, agent_goal: str | None = None,
             subject_id: str | None = None, trace_id: str | None = None,
             session_id: str | None = None) -> dict[str, Any]:
    return _call("mirror_user_intent", {"user_message": user_message,
                                        "conversation_context": conversation_context or [],
                                        "available_memory_refs": available_memory_refs or [],
                                        "agent_goal": agent_goal, "subject_id": subject_id,
                                        "trace_id": trace_id, "session_id": session_id})


@mcp.tool(name="build_jev_profile", title="Build Jev profile",
          description=TOOLS["build_jev_profile"].description)
def t_jev(context: str = "", subject: dict[str, Any] | None = None,
          known_preferences: dict[str, str] | None = None,
          recent_interactions: list[str] | None = None,
          memory_refs: list[str] | None = None, persist: bool = False,
          consent: bool = False, trace_id: str | None = None,
          session_id: str | None = None) -> dict[str, Any]:
    return _call("build_jev_profile", {"subject": subject or {}, "context": context,
                                       "known_preferences": known_preferences or {},
                                       "recent_interactions": recent_interactions or [],
                                       "memory_refs": memory_refs or [], "persist": persist,
                                       "consent": consent, "trace_id": trace_id,
                                       "session_id": session_id})


@mcp.tool(name="recommend_next_action", title="Recommend next action",
          description=TOOLS["recommend_next_action"].description)
def t_next(intent_summary: str = "", jev_profile: dict[str, Any] | None = None,
           business_goal: str | None = None, risk_level: str | None = None,
           available_tools: list[str] | None = None,
           guardrail_result: dict[str, Any] | None = None, trace_id: str | None = None,
           session_id: str | None = None) -> dict[str, Any]:
    return _call("recommend_next_action", {"intent_summary": intent_summary,
                                           "jev_profile": jev_profile,
                                           "business_goal": business_goal,
                                           "risk_level": risk_level,
                                           "available_tools": available_tools or [],
                                           "guardrail_result": guardrail_result,
                                           "trace_id": trace_id, "session_id": session_id})


@mcp.tool(name="frame_decision", title="Frame decision",
          description=TOOLS["frame_decision"].description)
def t_frame(decision_question: str, context: str = "",
            constraints: list[str] | None = None, success_metrics: list[str] | None = None,
            options: list[str] | None = None, trace_id: str | None = None,
            session_id: str | None = None) -> dict[str, Any]:
    return _call("frame_decision", {"decision_question": decision_question, "context": context,
                                    "constraints": constraints or [],
                                    "success_metrics": success_metrics or [],
                                    "options": options or [], "trace_id": trace_id,
                                    "session_id": session_id})


@mcp.tool(name="assess_business_impact", title="Assess business impact",
          description=TOOLS["assess_business_impact"].description)
def t_impact(request: str, target_workflow: str | None = None,
             stakeholders: list[str] | None = None,
             baseline: dict[str, Any] | None = None, trace_id: str | None = None,
             session_id: str | None = None) -> dict[str, Any]:
    return _call("assess_business_impact", {"request": request,
                                            "target_workflow": target_workflow,
                                            "stakeholders": stakeholders or [],
                                            "baseline": baseline or {}, "trace_id": trace_id,
                                            "session_id": session_id})


@mcp.tool(name="check_guardrails", title="Check guardrails",
          description=TOOLS["check_guardrails"].description)
def t_guard(planned_action: str, data_used: list[str] | None = None,
            user_context: dict[str, Any] | None = None, policy_profile: str | None = None,
            trace_id: str | None = None,
            session_id: str | None = None) -> dict[str, Any]:
    return _call("check_guardrails", {"planned_action": planned_action,
                                      "data_used": data_used or [],
                                      "user_context": user_context or {},
                                      "policy_profile": policy_profile, "trace_id": trace_id,
                                      "session_id": session_id})


@mcp.tool(name="memory_store", title="Store memory",
          description=TOOLS["memory_store"].description)
def t_mstore(subject_id: str, content: str, kind: str = "context", consent: bool = False,
             ttl_days: int | None = None, tags: list[str] | None = None,
             trace_id: str | None = None) -> dict[str, Any]:
    return _call("memory_store", {"subject_id": subject_id, "content": content, "kind": kind,
                                  "consent": consent, "ttl_days": ttl_days,
                                  "tags": tags or [], "trace_id": trace_id})


@mcp.tool(name="memory_recall", title="Recall memory",
          description=TOOLS["memory_recall"].description)
def t_mrecall(subject_id: str, query: str = "", refs: list[str] | None = None,
              kind: str = "any", limit: int = 10,
              trace_id: str | None = None) -> dict[str, Any]:
    return _call("memory_recall", {"subject_id": subject_id, "query": query,
                                   "refs": refs or [], "kind": kind, "limit": limit,
                                   "trace_id": trace_id})


@mcp.tool(name="memory_forget", title="Forget memory",
          description=TOOLS["memory_forget"].description)
def t_mforget(subject_id: str, ref: str | None = None,
              trace_id: str | None = None) -> dict[str, Any]:
    assert SERVICE is not None
    return SERVICE.call_as("memory_forget", {"subject_id": subject_id, "ref": ref,
                                             "trace_id": trace_id}, ROLE)


@mcp.tool(name="get_shared_context", title="Get shared context",
          description=TOOLS["get_shared_context"].description)
def t_shared(session_id: str | None = None,
             trace_id: str | None = None) -> dict[str, Any]:
    return _call("get_shared_context", {"session_id": session_id, "trace_id": trace_id})


@mcp.tool(name="record_feedback", title="Record feedback",
          description=TOOLS["record_feedback"].description)
def t_feedback(request_id: str, rating: int, useful: bool = True,
               outcome: str = "unknown", comment: str = "",
               trace_id: str | None = None) -> dict[str, Any]:
    return _call("record_feedback", {"request_id": request_id, "rating": rating,
                                     "useful": useful, "outcome": outcome, "comment": comment,
                                     "trace_id": trace_id})


@mcp.tool(name="get_tool_schemas", title="Get tool schemas",
          description=TOOLS["get_tool_schemas"].description)
def t_schemas(tool: str | None = None,
              trace_id: str | None = None) -> dict[str, Any]:
    return _call("get_tool_schemas", {"tool": tool, "trace_id": trace_id})


@mcp.tool(name="get_audit_trail", title="Get audit trail",
          description=TOOLS["get_audit_trail"].description)
def t_audit(request_id: str | None = None, filter_trace_id: str | None = None,
            tool: str | None = None, limit: int = 50,
            trace_id: str | None = None) -> dict[str, Any]:
    return _call("get_audit_trail", {"request_id": request_id,
                                     "filter_trace_id": filter_trace_id, "tool": tool,
                                     "limit": limit, "trace_id": trace_id})


@mcp.tool(name="list_policy_profiles", title="List policy profiles",
          description=TOOLS["list_policy_profiles"].description)
def t_policies(trace_id: str | None = None) -> dict[str, Any]:
    return _call("list_policy_profiles", {"trace_id": trace_id})


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - entrypoint
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "streamable-http", "sse"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    configure(load_settings())
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":  # pragma: no cover - legacy transport
        mcp.run(transport="sse", mount_path=None)
    else:
        import uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
