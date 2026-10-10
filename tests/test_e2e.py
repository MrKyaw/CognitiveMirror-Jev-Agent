"""End-to-end PRD workflow + MCP discovery (run with `make e2e`)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store


def _svc() -> Service:
    s = load_settings({"CM_DB_PATH": ":memory:"})
    return Service(s, Store(":memory:"), load_lexicon())


def test_prd_workflow_personal_agent():
    svc = _svc()
    trace, sess = "tr_e2e_personal", "e2e_personal"
    mirror = svc.call("mirror_user_intent", {
        "user_message": "Draft a follow-up email to my hiring manager about tomorrow's interview",
        "trace_id": trace, "session_id": sess}, "agent")
    assert "error" not in mirror
    jev = svc.call("build_jev_profile", {
        "subject": {"type": "user"}, "context": "Interview follow-up",
        "trace_id": trace, "session_id": sess}, "agent")
    assert "error" not in jev
    guard = svc.call("check_guardrails", {
        "planned_action": "Draft the follow-up email", "trace_id": trace}, "agent")
    assert "error" not in guard
    action = svc.call("recommend_next_action", {
        "intent_summary": mirror["result"], "jev_profile": jev["result"],
        "business_goal": "Get the offer", "available_tools": ["gmail"],
        "guardrail_result": guard["result"], "trace_id": trace,
        "session_id": sess}, "agent")
    assert "error" not in action
    assert action["result"]["business_impact"]
    assert action["result"]["agent_instruction"]
    shared = svc.call("get_shared_context", {"session_id": sess}, "agent")
    assert len(shared["result"]["entries"]) >= 3
    # feedback + audit traceability
    fb = svc.call("record_feedback", {
        "request_id": mirror["request_id"], "rating": 5}, "agent")
    assert fb["result"]["request_found"]


def test_prd_workflow_enterprise_guardrail_flags():
    svc = _svc()
    guard = svc.call("check_guardrails", {
        "planned_action": "Email all customers their contracts and wire the $9k refund",
        "data_used": ["customer list"]}, "agent")
    assert guard["result"]["human_approval_required"]
    decision = svc.call("frame_decision", {
        "decision_question": "Should we switch vendors or renew?"}, "agent")
    assert decision["result"]["recommended_option"]
    impact = svc.call("assess_business_impact", {
        "request": "Switch vendors for support"}, "agent")
    assert impact["result"]["priority_score"] >= 0


@pytest.mark.asyncio()
async def test_mcp_tool_discovery():
    from cognitive_mirror import mcp_server as ms
    ms.configure(load_settings({"CM_DB_PATH": ":memory:"}))
    tools = await ms.mcp.list_tools()
    names = {t.name for t in tools}
    assert {"mirror_user_intent", "build_jev_profile", "recommend_next_action",
            "frame_decision", "assess_business_impact", "check_guardrails"} <= names
    assert len(names) == 14
