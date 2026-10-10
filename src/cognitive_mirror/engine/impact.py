"""assess_business_impact (PRD 8.5). Pure and offline."""
from __future__ import annotations

from cognitive_mirror.engine import EngineOutput
from cognitive_mirror.engine.lexicons import Lexicon
from cognitive_mirror.engine.text import clip, find_phrases, normalize, truncate
from cognitive_mirror.models import AssessBusinessImpactInput, Epistemics


def assess_business_impact(inp: AssessBusinessImpactInput, lex: Lexicon) -> EngineOutput:
    text = normalize(f"{inp.request} {inp.target_workflow or ''} {' '.join(inp.stakeholders)}")
    cats = lex["impact_categories"]
    scored: list[tuple[str, int]] = []
    for name, spec in cats.items():
        hits = find_phrases(text, spec["terms"])
        if hits:
            scored.append((name, len(hits)))
    scored.sort(key=lambda t: (-t[1], t[0]))
    primary = scored[0][0] if scored else "productivity"
    secondary = [n for n, _ in scored[1:3]]

    spec = cats[primary]
    benefits = list(spec["benefits"])[:2]
    metrics = []
    for m in spec["metrics"][:3]:
        baseline = None
        for key, val in inp.baseline.items():
            if isinstance(val, (int, float)):
                klow = normalize(key)
                if any(kw in klow or klow in kw or klow.rstrip("s") in kw or kw in klow.rstrip("s")
                       for kw in m["keywords"]):
                    baseline = float(val)
                    break
        delta = m["delta"]
        sign = "+" if delta > 0 else ""
        metrics.append({"metric": m["metric"], "baseline": baseline,
                        "expected_delta": f"{sign}{int(delta * 100)}%",
                        "target": round(baseline * (1 + delta), 2) if baseline is not None else None,
                        "confidence": 0.6 if baseline is not None else 0.45,
                        "evidence": spec["mechanism"]})

    effort_level = "low" if len(text.split()) < 20 else ("medium" if len(text.split()) < 60 else "high")
    priority = clip(0.5 + 0.1 * len(scored) + (0.1 if inp.baseline else 0.0)
                    + (0.1 if inp.stakeholders else 0.0), 0.05, 0.95)
    result = {
        "impact_category": primary,
        "secondary_categories": secondary,
        "expected_benefits": benefits,
        "metrics": metrics,
        "cost_or_effort": {"level": effort_level,
                           "estimate": f"{effort_level} effort for {inp.target_workflow or 'workflow'}",
                           "drivers": ["scope size", "stakeholder count"]},
        "roi_hypothesis": f"If {truncate(inp.request, 80)}, then {spec['mechanism']}, "
                          f"improving {metrics[0]['metric']} by {metrics[0]['expected_delta']}",
        "priority_score": round(priority * 100),
        "stakeholder_impact": [{"stakeholder": s, "impact": truncate(spec["mechanism"], 160)}
                               for s in inp.stakeholders[:10]],
    }
    epistemics = Epistemics(
        facts=[f"Matched category: {primary}"],
        assumptions=([] if inp.baseline else ["No baseline provided; deltas are hypotheses"]),
        inferences=[f"Priority {result['priority_score']}/100 from {len(scored)} signals"],
        recommendations=[f"Track {metrics[0]['metric']} before/after"],
    )
    return EngineOutput(result, clip(sum(m["confidence"] for m in metrics) / len(metrics)),
                        epistemics, [{"source": "request", "quote": truncate(inp.request, 120)}])
