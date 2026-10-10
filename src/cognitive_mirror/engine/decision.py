"""frame_decision (PRD 8.4). Pure and offline."""
from __future__ import annotations

from cognitive_mirror.engine import EngineOutput
from cognitive_mirror.engine.lexicons import Lexicon
from cognitive_mirror.engine.text import clip, find_phrases, normalize, truncate
from cognitive_mirror.models import Epistemics, FrameDecisionInput


def _decision_type(q: str) -> str:
    if find_phrases(q, ["when", "timing", "now or later", "deadline"]):
        return "timing"
    if find_phrases(q, ["budget", "allocate", "resource", "spend", "hire"]):
        return "resource_allocation"
    if find_phrases(q, ["should i", "should we", "or not", "whether to"]):
        return "binary"
    return "selection"


def frame_decision(inp: FrameDecisionInput, lex: Lexicon) -> EngineOutput:
    q = normalize(inp.decision_question)
    dtype = _decision_type(q)
    irreversible = bool(find_phrases(q, ["quit", "fire", "sign the contract", "irreversible",
                                         "resign", "delete", "launch", "publish", "accept the offer"]))
    stakes = "high" if irreversible or find_phrases(q, ["job", "offer", "contract", "salary",
                                                        "layoff", "investment"]) else (
        "medium" if inp.constraints or inp.success_metrics else "low")

    criteria = []
    for i, metric in enumerate(inp.success_metrics[:5]):
        criteria.append({"name": truncate(metric, 80), "weight": round(0.6 - i * 0.05, 3),
                         "source": "success_metric"})
    for constraint in inp.constraints[:3]:
        criteria.append({"name": truncate(f"Respect: {constraint}", 80), "weight": 0.3,
                         "source": "constraint"})
    if not criteria:
        criteria = [{"name": "Outcome quality", "weight": 0.5, "source": "default"},
                    {"name": "Effort and reversibility", "weight": 0.3, "source": "default"}]

    names = list(inp.options[:10]) or ["Proceed", "Gather more information", "Defer"]
    if "Gather more information" not in names:
        names.append("Gather more information")
    if "Defer" not in names:
        names.append("Defer")
    names = names[:10]

    options = []
    for i, name in enumerate(names):
        is_info = "information" in name.lower()
        is_defer = name.lower() == "defer"
        base = 0.55 - i * 0.03
        if is_info and (not inp.constraints or stakes == "high"):
            base += 0.15
        scores = {c["name"]: round(clip(base + (0.05 if k % 2 == 0 else -0.03)), 3)
                  for k, c in enumerate(criteria)}
        total = round(sum(scores[c["name"]] * c["weight"] for c in criteria)
                      / max(sum(c["weight"] for c in criteria), 1e-9), 3)
        options.append({"id": f"opt_{i + 1}", "name": truncate(name, 120),
                        "description": truncate(f"Option: {name}", 300),
                        "scores": scores, "total_score": clip(total),
                        "pros": ["Keeps momentum"] if not is_defer else ["Preserves optionality"],
                        "cons": ["Acts on incomplete info"] if not is_info and stakes == "high"
                        else ["Takes more time"]})
    options.sort(key=lambda o: -o["total_score"])
    tradeoffs = [{"between": [options[0]["id"], options[1]["id"]],
                  "description": f"{options[0]['name']} is faster; "
                                 f"{options[1]['name']} is safer"}]
    risks = [{"risk": "Choosing with incomplete information", "option_id": options[0]["id"],
              "likelihood": "medium", "impact": "high" if stakes == "high" else "medium",
              "mitigation": "Timebox information gathering, then decide"}]
    result = {
        "decision_frame": {"question": truncate(inp.decision_question, 500),
                           "decision_type": dtype,
                           "reversibility": "hard_to_reverse" if irreversible else "reversible",
                           "stakes": stakes, "criteria": criteria,
                           "constraints": inp.constraints[:30]},
        "options": options,
        "tradeoffs": tradeoffs,
        "risk_register": risks,
        "recommended_option": options[0]["id"],
        "rationale": f"Highest weighted score ({options[0]['total_score']}) on {len(criteria)} criteria",
    }
    epistemics = Epistemics(
        facts=[f"Options considered: {len(options)}", f"Stakes: {stakes}"],
        assumptions=(["No success metrics given; using defaults"] if not inp.success_metrics else []),
        inferences=[f"Decision type: {dtype}"],
        recommendations=[f"Recommend {options[0]['name']}"],
    )
    return EngineOutput(result, clip(0.65 if inp.success_metrics else 0.5),
                        epistemics, [{"source": "decision_question",
                                       "quote": truncate(inp.decision_question, 120)}])
