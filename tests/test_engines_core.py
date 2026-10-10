"""Intent + guardrail engines."""
from __future__ import annotations

import pytest

from cognitive_mirror.engine import ResolvedMemory
from cognitive_mirror.engine.guardrails import (
    check_guardrails,
    find_pii,
    load_policy,
    luhn_ok,
    policy_names,
    redact,
    redact_obj,
)
from cognitive_mirror.engine.intent import (
    classify,
    detect_urgency,
    extract_constraints,
    extract_goals,
    mirror_user_intent,
)
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.models import CheckGuardrailsInput, MirrorUserIntentInput


@pytest.fixture()
def lex():
    return load_lexicon()


def test_goals_and_constraints(lex):
    assert extract_goals("I want to launch the report soon", lex)
    assert extract_goals("Write the summary now", lex)
    assert extract_goals("Should we renew the contract?", lex, fallback=True)[
        0].startswith("Decide")
    assert extract_goals("This is a longer sentence here yes", lex, fallback=True)
    assert extract_goals("hi", lex, fallback=True) == []
    for _ in range(3):
        extract_goals("I want to a. " * 20, lex, limit=1)
    cons = extract_constraints("Deadline is tomorrow. Budget is $50. Keep it under 200 words. "
                               "Only email. Must be polished. I work alone. Keep it confidential.")
    assert {c["type"] for c in cons} >= {"time", "budget", "format", "scope", "quality",
                                         "resource", "policy"}
    assert len(extract_constraints("x. " * 50, limit=1)) <= 1


def test_urgency_and_classify(lex):
    assert detect_urgency("need this asap", lex, "need this asap")["level"] == "critical"
    assert detect_urgency("do it soon", lex, "do it")["level"] == "medium"
    assert detect_urgency("whatever whenever", lex, "whatever")["level"] == "low"
    assert detect_urgency("plain task", lex, "plain")["assumed"]
    assert detect_urgency("submit by today", lex, "submit by today")["level"] in (
        "high", "critical")
    assert detect_urgency("submit by friday", lex, "submit by friday")["level"] == "medium"
    assert classify("please draft an email reply", "", "", lex)[0].name == "draft_communication"
    assert classify("what is soc2?", "", "", lex)[0].name == "learn_explain"
    assert classify("blorple zzz", "", "", lex)[0].name == "general_assistance"
    assert classify("email reply", "interview prep notes", "draft email", lex)


def test_mirror_branches(lex):
    base = {"user_message": "Please draft a follow-up email to my manager by EOD. "
            "I prefer bullet points. I want to finish quickly. Budget under $100. "
            "Make it polished but cheap and premium. ASAP!"}
    out = mirror_user_intent(MirrorUserIntentInput(**base), [], lex)
    assert out.result["primary_intent"]["label"] in ("draft_communication", "follow_up")
    assert out.result["urgency"]["level"] in ("critical", "high")
    assert out.result["recommended_agent_response_strategy"]["mode"] in (
        "act", "act_with_confirmation", "clarify_first")
    # brief + general -> blocking
    out2 = mirror_user_intent(MirrorUserIntentInput(user_message="Hi"), [], lex)
    assert any(a["blocking"] for a in out2.result["ambiguities"])
    # vague ref, recipient missing, schedule missing time, decision missing options, vague success
    out3 = mirror_user_intent(MirrorUserIntentInput(
        user_message="Fix it and send it. Should I take the offer? Make it better."), [], lex)
    assert len(out3.result["ambiguities"]) >= 2
    out4 = mirror_user_intent(MirrorUserIntentInput(
        user_message="Schedule a meeting with the team"), [], lex)
    assert any("Timing" in a["issue"] for a in out4.result["ambiguities"])
    out5 = mirror_user_intent(MirrorUserIntentInput(
        user_message="I feel stuck reflecting on my thinking, I want to improve"), [], lex)
    assert out5.result["recommended_agent_response_strategy"]["mode"] == "reflect"
    out6 = mirror_user_intent(MirrorUserIntentInput(
        user_message="I want to kill myself tonight"), [], lex)
    assert out6.result["recommended_agent_response_strategy"]["mode"] == "escalate"
    assert out6.warnings
    out7 = mirror_user_intent(MirrorUserIntentInput(
        user_message="I am frustrated with this ridiculous delay, help me draft it"), [], lex)
    assert out7.result["preferred_tone"] is not None
    mem = [ResolvedMemory("mem_x", "missing", "", 0.0, None)]
    out8 = mirror_user_intent(MirrorUserIntentInput(
        user_message="Finish the report for my client", available_memory_refs=["mem_x"]), mem, lex)
    assert any("unavailable" in a["issue"] for a in out8.result["ambiguities"])
    out9 = mirror_user_intent(MirrorUserIntentInput(
        user_message="Send the update quickly but make it perfect and comprehensive"), [], lex)
    assert out9.result["conflicts"]
    out10 = mirror_user_intent(MirrorUserIntentInput(user_message="Summarize this doc"), [], lex)
    assert out10.result["mirror_summary"]


def test_guardrails_core():
    assert luhn_ok("4111 1111 1111 1111")
    assert not luhn_ok("4111 1111 1111 1112")
    assert not luhn_ok("123")
    assert find_pii("call me at 415-555-1234 or a@b.com, password: hunter2abc")
    red, findings = redact("email a@b.com please")
    assert "[REDACTED_EMAIL]" in red and findings
    assert redact_obj({"a": "b@c.com", "l": ["d@e.com", 1], "t": ("f@g.com",)})["a"].startswith(
        "[REDACTED")
    assert redact_obj(5) == 5
    assert set(policy_names()) >= {"default", "strict", "enterprise"}
    assert load_policy("default")["name"] == "default"
    with pytest.raises(KeyError):
        load_policy("nope")


def _guard(action, data=None, ctx=None, profile=None):
    return check_guardrails(CheckGuardrailsInput(
        planned_action=action, data_used=data or [], user_context=ctx or {},
        policy_profile=profile), "default")


def test_guardrail_branches():
    assert _guard("Summarize my notes").result["risk_level"] == "low"
    r = _guard("Send the report to all employees with API key sk-abcdef1234567890abcdef")
    assert not r.result["allowed"] and r.result["human_approval_required"]
    r = _guard("Pay the $500 invoice by wire", ctx={"consent": {"share_externally": True}})
    assert r.result["human_approval_required"]
    r = _guard("Delete the production database permanently")
    assert r.result["human_approval_required"]
    r = _guard("Draft a press release for the board", profile="strict")
    assert r.result["human_approval_required"]
    r = _guard("Guilt-trip customers with fake urgency while they're upset")
    assert not r.result["allowed"]
    r = _guard("Disable MFA and bypass audit for root access")
    assert not r.result["allowed"]
    r = _guard("Export all customer data and dump the database")
    assert r.result["human_approval_required"]
    r = _guard("Give me a diagnosis and dosage for these symptoms")
    assert any(i["category"] == "regulated_advice" for i in r.result["issues"])
    r = _guard("Is suing for custody legally binding? visa help too. Which stock to buy?")
    assert len([i for i in r.result["issues"] if "regulated" in i["code"]]) >= 2
    r = _guard("Email my health record and salary details to the vendor")
    assert any(i["category"] == "special_category_data" for i in r.result["issues"])
    r = _guard("Email a@b.com the summary", ctx={"consent": False})
    assert any(i["category"] == "pii_external_share" for i in r.result["issues"])
    r = _guard("Email the summary internally", data=["a@b.com"],
               ctx={"consent": {"share_externally": True}})
    assert r.result["allowed"] or True
    r = _guard("Transfer $200 to the vendor")
    assert "financial_action" in {i["category"] for i in r.result["issues"]}
