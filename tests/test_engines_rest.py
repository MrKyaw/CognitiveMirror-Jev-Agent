"""Jev, actions, decision, impact engines."""
from __future__ import annotations

import pytest

from cognitive_mirror.engine import ResolvedMemory
from cognitive_mirror.engine.actions import recommend_next_action
from cognitive_mirror.engine.decision import frame_decision
from cognitive_mirror.engine.impact import assess_business_impact
from cognitive_mirror.engine.jev import build_jev_profile
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.models import (
    AssessBusinessImpactInput,
    BuildJevProfileInput,
    FrameDecisionInput,
    RecommendNextActionInput,
)


@pytest.fixture()
def lex():
    return load_lexicon()


def test_jev(lex):
    o = build_jev_profile(BuildJevProfileInput(
        context="I am a senior engineer deciding between two offers, feeling anxious",
        known_preferences={"tone": "concise", "health": "x"},
        recent_interactions=["interview yesterday"]), [], lex)
    assert o.result["persona_signals"]["expertise_level"] == "expert"
    assert o.result["journey_stage"]["stage"] == "deciding"
    assert o.result["emotion_signals"]
    assert o.result["ignored_sensitive_attributes"] == ["health"]
    o2 = build_jev_profile(BuildJevProfileInput(
        subject={"role": "founder"}, context="launch plan"), [], lex)
    assert o2.result["persona_signals"]["role"] == "founder"
    o3 = build_jev_profile(BuildJevProfileInput(context="trick them with guilt"), [], lex)
    assert any("neutrally" in s for s in o3.result["autonomy_safeguards"])
    assert o3.warnings
    mem = [ResolvedMemory("m1", "resolved", "prefers concise", 0.9, 1.0)]
    o4 = build_jev_profile(BuildJevProfileInput(context="status update"), mem, lex)
    assert o4.result["memory_used"][0]["ref"] == "m1"
    o5 = build_jev_profile(BuildJevProfileInput(context=""), [], lex)
    assert o5.result["persona_signals"]["role"] is None
    o6 = build_jev_profile(BuildJevProfileInput(context="I failed the interview, feeling bad"), [],
                           lex)
    assert o6.result["journey_stage"]["stage"] == "recovering"


def test_actions(lex):
    o = recommend_next_action(RecommendNextActionInput(
        intent_summary="Please draft an email to the client", business_goal="Close the deal",
        available_tools=["gmail"]), lex)
    assert o.result["recommended_action"]["type"] == "draft"
    o2 = recommend_next_action(RecommendNextActionInput(intent_summary="What?"), lex)
    assert o2.result["recommended_action"]["type"] == "clarify"
    o3 = recommend_next_action(RecommendNextActionInput(
        intent_summary={"mirror_summary": "draft email", "explicit_goals": ["Send update"],
                        "recommended_agent_response_strategy": {"mode": "act"},
                        "primary_intent": {"label": "draft"}},
        guardrail_result={"human_approval_required": True, "allowed": False}), lex)
    assert o3.result["human_approval_required"]
    o4 = recommend_next_action(RecommendNextActionInput(
        intent_summary="Reduce compliance risk", risk_level="critical",
        available_tools=["ANALYTICS"]), lex)
    assert o4.result["risks"]
    o5 = recommend_next_action(RecommendNextActionInput(intent_summary="", business_goal=""), lex)
    assert o5.result["agent_instruction"]
    o6 = recommend_next_action(RecommendNextActionInput(
        intent_summary="analyze churn data", business_goal="Grow revenue"), lex)
    assert o6.result["business_impact"]["category"] == "revenue"


def test_decision(lex):
    o = frame_decision(FrameDecisionInput(
        decision_question="Should we accept the job offer?",
        constraints=["Must decide by Friday"], success_metrics=["Salary growth"]), lex)
    assert o.result["decision_frame"]["decision_type"] == "binary"
    assert o.result["recommended_option"].startswith("opt_")
    o2 = frame_decision(FrameDecisionInput(
        decision_question="When should we launch given the deadline?",
        options=["Launch now", "Wait"]), lex)
    assert o2.result["decision_frame"]["decision_type"] == "timing"
    o3 = frame_decision(FrameDecisionInput(
        decision_question="How to allocate the hiring budget across teams?"), lex)
    assert o3.result["decision_frame"]["decision_type"] == "resource_allocation"
    o4 = frame_decision(FrameDecisionInput(decision_question="Which vendor is best?"), lex)
    assert o4.result["decision_frame"]["stakes"] == "low"
    o5 = frame_decision(FrameDecisionInput(
        decision_question="Should I resign and quit tomorrow?",
        success_metrics=["Happiness"]), lex)
    assert o5.result["decision_frame"]["reversibility"] == "hard_to_reverse"


def test_impact(lex):
    o = assess_business_impact(AssessBusinessImpactInput(
        request="Automate the weekly reporting workflow to save hours",
        target_workflow="reporting", stakeholders=["analysts"],
        baseline={"hours_per_week": 10}), lex)
    assert o.result["impact_category"] == "productivity"
    assert o.result["metrics"][0]["target"] == pytest.approx(7.5)
    o2 = assess_business_impact(AssessBusinessImpactInput(
        request="Grow revenue with better conversion on deals"), lex)
    assert o2.result["impact_category"] == "revenue"
    o3 = assess_business_impact(AssessBusinessImpactInput(request="zzz qqq"), lex)
    assert o3.result["impact_category"] == "productivity"
    o4 = assess_business_impact(AssessBusinessImpactInput(
        request="A very long request " + "word " * 80, stakeholders=["a", "b"]), lex)
    assert o4.result["cost_or_effort"]["level"] == "high"
