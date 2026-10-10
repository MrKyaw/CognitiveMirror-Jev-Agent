"""recommend_next_action (PRD 8.3, AGENT-003/005). Pure and offline."""
from __future__ import annotations

from typing import Any

from cognitive_mirror.engine import EngineOutput
from cognitive_mirror.engine.lexicons import Lexicon
from cognitive_mirror.engine.text import clip, find_phrases, normalize, truncate
from cognitive_mirror.models import Epistemics, RecommendNextActionInput

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _intent_text(intent_summary: str | dict[str, Any]) -> str:
    if isinstance(intent_summary, dict):
        parts = []
        for key in ("mirror_summary", "desired_output", "primary_intent"):
            val = intent_summary.get(key)
            if isinstance(val, dict):
                val = val.get("label", "")
            if val:
                parts.append(str(val))
        goals = intent_summary.get("explicit_goals", [])
        if isinstance(goals, list):
            parts.extend(str(g) for g in goals[:2])
        strategy = intent_summary.get("recommended_agent_response_strategy", {})
        if isinstance(strategy, dict) and strategy.get("mode"):
            parts.append(str(strategy["mode"]))
        return " ".join(parts)
    return str(intent_summary or "")


def recommend_next_action(inp: RecommendNextActionInput, lex: Lexicon) -> EngineOutput:
    summary_txt = normalize(_intent_text(inp.intent_summary))
    goal_txt = normalize(inp.business_goal or "")
    guard = inp.guardrail_result or {}
    guard_approval = bool(guard.get("human_approval_required"))
    guard_blocked = guard.get("allowed") is False
    declared = (inp.risk_level or "").lower()
    base_risk = declared if declared in _RISK_ORDER else None

    candidates: list[tuple[str, str, str]] = []  # action, type, why
    for name, spec in lex["intents"].items():
        action = spec.get("action", {})
        keywords = [k for k in spec.get("keywords", []) if len(k) > 2]
        if find_phrases(summary_txt or goal_txt, keywords):
            candidates.append((action.get("action", name.replace("_", " ")),
                               action.get("type", "plan"), name))
    if not candidates:
        if "?" in summary_txt and len(summary_txt.split()) < 12:
            candidates.append(("Ask one clarifying question before acting", "clarify", "general"))
        else:
            candidates.append(("Produce the deliverable directly, leading with the answer",
                               "draft", "general"))

    top_action, top_type, _why = candidates[0]
    tool_match: str | None = None
    if inp.available_tools:
        low_tools = {t.lower(): t for t in inp.available_tools}
        for name, spec in lex["intents"].items():
            for kw in spec.get("action", {}).get("tool_keywords", []):
                for low, original in low_tools.items():
                    if kw in low and tool_match is None:
                        tool_match = original
        tool_match = tool_match or inp.available_tools[0]
    if top_type == "clarify":
        tool_match = None

    needs_approval = guard_approval or guard_blocked
    reason: str | None = "Guardrail requires human approval" if needs_approval else None
    risk_label = base_risk or ("high" if needs_approval else "medium" if top_type == "draft" else "low")

    impact_cat = "productivity"
    if find_phrases(goal_txt or summary_txt, lex["impact_categories"]["revenue"]["terms"]):
        impact_cat = "revenue"
    elif find_phrases(goal_txt or summary_txt, lex["impact_categories"]["risk_reduction"]["terms"]):
        impact_cat = "risk_reduction"
    metric = {"productivity": "turns to completion",
              "revenue": "conversion rate",
              "risk_reduction": "incidents or policy exceptions"}[impact_cat]

    alternatives = [{"action": a, "type": t, "tool": tool_match, "description": truncate(a, 200)}
                    for a, t, _ in candidates[1:3]]
    if top_type != "clarify":
        alternatives.append({"action": "Ask a clarifying question if the draft would miss",
                             "type": "clarify", "tool": None,
                             "description": "Fallback when confidence is low"})
    alternatives = alternatives[:2]

    instruction = truncate(f"{top_action}. Context: {(_intent_text(inp.intent_summary) or 'n/a')[:300]}"
                           + (f" Business goal: {inp.business_goal[:200]}" if inp.business_goal else "")
                           + (" Get human approval first." if needs_approval else ""), 800)
    result = {
        "recommended_action": {"action": truncate(top_action, 300), "type": top_type,
                               "tool": tool_match, "description": truncate(top_action, 300)},
        "alternative_actions": alternatives,
        "business_impact": {"category": impact_cat,
                            "summary": f"Expected {impact_cat.replace('_', ' ')} gain",
                            "metric": metric},
        "risks": (["Guardrail blocked or needs approval"] if needs_approval else [])
        + ([f"Declared risk level: {declared}"] if declared else []),
        "human_approval_required": needs_approval,
        "approval_reason": reason,
        "agent_instruction": instruction,
    }
    conf = clip(0.7 if candidates and _why != "general" else 0.5, 0.05, 0.95)
    epistemics = Epistemics(
        facts=[f"Intent summary chars: {len(str(inp.intent_summary))}"],
        assumptions=([] if inp.intent_summary else ["No intent summary; using generic default"]),
        inferences=[f"Matched playbook: {_why}", f"Risk: {risk_label}"],
        recommendations=[top_action],
    )
    return EngineOutput(result, conf, epistemics,
                        [{"source": "intent_summary",
                          "quote": truncate(str(inp.intent_summary)[:120], 120)}])
