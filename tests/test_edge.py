"""Edge branches to reach 100% coverage."""
from __future__ import annotations

from fastapi.testclient import TestClient

from cognitive_mirror.api import create_app
from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.guardrails import _mask, check_guardrails, find_pii
from cognitive_mirror.engine.intent import (
    classify,
    detect_urgency,
    extract_constraints,
    extract_goals,
    mirror_user_intent,
)
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.engine.text import find_phrases
from cognitive_mirror.models import CheckGuardrailsInput, MirrorUserIntentInput
from cognitive_mirror.store import Store


def test_api_edge():
    s = load_settings({"CM_DB_PATH": ":memory:", "CM_ALLOWED_HOSTS": "example.com"})
    c = TestClient(create_app(s))
    # malformed Authorization (no 2 parts) -> falls through to invalid key -> 401
    r = c.post("/v1/tools/mirror_user_intent", json={"user_message": "Summarize fully now"},
               headers={"Authorization": "Bogus", "Host": "example.com"})
    assert r.status_code == 401
    # allowed host passes
    r = c.post("/v1/tools/mirror_user_intent",
               json={"user_message": "Summarize the quarterly report fully"},
               headers={"X-API-Key": "dev-agent-key", "Host": "example.com"})
    assert r.status_code == 200


def test_actions_edge():
    from cognitive_mirror.engine.actions import recommend_next_action
    from cognitive_mirror.models import RecommendNextActionInput
    lex = load_lexicon()
    o = recommend_next_action(RecommendNextActionInput(
        intent_summary={"explicit_goals": "notalist",
                        "recommended_agent_response_strategy": "act"}), lex)
    assert o.result["agent_instruction"]
    o2 = recommend_next_action(RecommendNextActionInput(
        intent_summary={"mirror_summary": "x",
                        "recommended_agent_response_strategy": {"mode": ""}}), lex)
    assert o2.result


def test_guardrail_edge():
    assert _mask("abc") == "***"
    assert _mask("abcdef") == "ab**ef"
    # overlapping span: secret match first, embedded email skipped via `continue`
    hits = find_pii("password: a@b.com")
    assert any(h.type == "secret" for h in hits)
    assert not any(h.type == "email" for h in hits)
    # invalid credit-card-like digits skipped via luhn `continue`
    hits = find_pii("card 4111 1111 1111 1112 here")
    assert all(h.type != "credit_card" for h in hits)
    # money + external without financial keyword adds financial_action
    r = check_guardrails(CheckGuardrailsInput(
        planned_action="Send the summary to the team for $500"), "default")
    assert "financial_action" in {i["category"] for i in r.result["issues"]}


def test_impact_edge():
    from cognitive_mirror.engine.impact import assess_business_impact
    from cognitive_mirror.models import AssessBusinessImpactInput
    lex = load_lexicon()
    o = assess_business_impact(AssessBusinessImpactInput(
        request="Do the thing", baseline={"unrelated_metric_xyz": 5, "note": "n/a"}), lex)
    assert o.result["metrics"][0]["baseline"] is None


def test_intent_edge():
    lex = load_lexicon()
    # goals limit break
    g = extract_goals("I want to a1 b1. I want to a2 b2. I want to a3 b3.", lex, limit=1)
    assert len(g) == 1
    # constraints limit break
    c = extract_constraints("Deadline x. " * 20, limit=1)
    assert len(c) == 1
    # urgency floor upgrade: low signal + same-day deadline
    u = detect_urgency("whenever no rush", lex, "whenever, submit by today")
    assert u["level"] in ("high", "critical")
    # unscored question -> learn_explain fallback
    scored = classify("Blorple zzz qqq?", "", "", lex)
    assert scored[0].name == "learn_explain"
    # duplicate phrase list hits `continue`
    assert find_phrases("email here", ["email", "email"]) == ["email"]
    # make_decision without options
    o = mirror_user_intent(MirrorUserIntentInput(user_message="Should I accept? Decide now"), [],
                           lex)
    assert any("Options" in a["issue"] for a in o.result["ambiguities"])
    # reflection: make_decision + disappointment
    o2 = mirror_user_intent(MirrorUserIntentInput(
        user_message="Should I stay or go? I am disappointed we lost the deal"), [], lex)
    prompts = " ".join(o2.result["reflection_prompts"])
    assert "confident" in prompts or "keep" in prompts
    # value driver without a mapped outcome exercises the `if outcome:` false branch
    lex2 = dict(lex)
    lex2["value_drivers"] = {"zzzdriver": ["zzzphrase"], **lex["value_drivers"]}
    o3 = mirror_user_intent(MirrorUserIntentInput(
        user_message="Please zzzphrase and summarize the report for real"), [], lex2)
    assert o3.result["business_outcomes"]


def test_store_file(tmp_path):
    s = Store(tmp_path / "nested" / "db.sqlite")
    ref, _ = s.memory_store("u", "hi", "context", [], None, [])
    assert s.memory_get(ref, "u")
