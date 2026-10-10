"""build_jev_profile (PRD 8.2, JEV-001..006). Pure and offline."""
from __future__ import annotations

from cognitive_mirror.engine import EngineOutput, ResolvedMemory, memory_coverage
from cognitive_mirror.engine.lexicons import Lexicon, best, score_dimension
from cognitive_mirror.engine.text import clip, find_phrases, normalize, saturate, truncate
from cognitive_mirror.models import BuildJevProfileInput, Epistemics

AUTONOMY_BASE = [
    "Present inferences as possibilities, not facts; let the user correct them",
    "Do not infer protected attributes (health, religion, ethnicity, politics, etc.)",
    "Prefer clarification over assumption when confidence is low",
]
SENSITIVE_KEYS = (
    "health", "medical", "diagnosis", "religion", "ethnicity", "race",
    "sexual_orientation", "sexuality", "political", "politics", "disability",
    "pregnancy", "immigration_status", "criminal_record", "union_membership",
    "biometric", "genetic",
)


def _role(all_text: str, lex: Lexicon, subject_role: str | None) -> str | None:
    if subject_role:
        return truncate(subject_role, 200)
    for role, phrases in lex["roles"].items():
        if find_phrases(all_text, phrases):
            return role
    return None


def _expertise(all_text: str, lex: Lexicon) -> str:
    for level in ("expert", "novice"):
        if find_phrases(all_text, lex["expertise"][level]):
            return level
    return "unknown"


def _comm_pref(all_text: str, lex: Lexicon) -> str:
    hit = best(all_text, lex["communication"])
    return hit.name if hit else "unknown"


def build_jev_profile(
    inp: BuildJevProfileInput, memory: list[ResolvedMemory], lex: Lexicon
) -> EngineOutput:
    ctx = normalize(" ".join([inp.context, *inp.recent_interactions]))
    pref_text = normalize(" ".join(f"{k} {v}" for k, v in inp.known_preferences.items()))
    mem_text = normalize(" ".join(m.content for m in memory if m.status == "resolved"))
    all_text = " ".join(t for t in (ctx, pref_text, mem_text) if t)

    role = _role(all_text, lex, inp.subject.role)
    expertise = _expertise(all_text, lex)
    comm = _comm_pref(all_text, lex)
    journey = best(all_text, lex["journey_stages"])
    stage = journey.name if journey else "exploring"
    stage_conf = clip(journey.score if journey else 0.3)
    stage_ev = list(journey.hits[:3]) if journey else []

    emotions = score_dimension(ctx or all_text, lex["emotions"])[:4]
    values = score_dimension(all_text or ctx, lex["value_drivers"],
                             weights=lex.get("value_weights"))[:4]
    manip = find_phrases(all_text, lex.get("manipulative_terms", []))

    judgment_need = "Clarify the goal and constraints" if stage in ("exploring", "deciding") else (
        "Confirm the plan before acting" if stage == "executing" else "Review progress and next step")
    key_qs = ["What outcome matters most here?", "What constraints cannot be broken?"]
    if stage == "deciding":
        key_qs = ["Which option best fits the stated values?", "What would change the choice?"]
    elif stage == "recovering":
        key_qs = ["What happened, and what is still in your control?", "What is one small next step?"]

    ignored = sorted({k for k in inp.known_preferences if k.lower() in SENSITIVE_KEYS})
    safeguards = list(AUTONOMY_BASE)
    if manip:
        safeguards.append("Refuse manipulative tactics; present options neutrally (JEV-006)")
    if ignored:
        safeguards.append(f"Ignored sensitive preference keys: {', '.join(ignored)}")

    coverage = memory_coverage(memory)
    confidence = clip(0.3 + 0.3 * saturate(len(ctx.split()) / 20.0)
                      + (0.0 if coverage is None else 0.2 * coverage)
                      + (0.1 if role else 0.0), 0.05, 0.95)

    result = {
        "persona_signals": {
            "role": role,
            "expertise_level": expertise,
            "goals": [truncate(g, 200) for g in
                      ([inp.context[:200]] if inp.context else ["Get useful help quickly"])][:3],
            "communication_preference": comm,
            "current_context": truncate(inp.context or "No context provided", 500),
        },
        "journey_stage": {"stage": stage, "confidence": stage_conf, "evidence": stage_ev},
        "emotion_signals": [{"name": e.name, "score": e.score, "evidence": list(e.hits[:2])}
                            for e in emotions],
        "value_drivers": [{"name": v.name, "score": v.score, "evidence": list(v.hits[:2])}
                          for v in values],
        "judgment_context": {
            "judgment_need": judgment_need,
            "key_questions": key_qs,
            "options_hint": ["Gather more information", "Proceed with best available option"],
            "risks": ["Acting on incomplete context"] if confidence < 0.5 else [],
            "recommended_next_steps": ["Mirror intent first (mirror_user_intent)"],
            "stakeholder_impact": [f"Subject type: {inp.subject.type}"],
        },
        "autonomy_safeguards": safeguards,
        "ignored_sensitive_attributes": ignored,
        "memory_used": [m.use() for m in memory],
        "profile_ref": None,
        "confidence": confidence,
    }
    epistemics = Epistemics(
        facts=[f"Context chars: {len(inp.context)}",
               f"Known preferences: {len(inp.known_preferences)}"],
        assumptions=(["No recent interactions; using context only"]
                     if not inp.recent_interactions else []),
        inferences=[f"Journey stage: {stage} ({stage_conf})",
                    f"Top value: {values[0].name}" if values else "No value signal"],
        recommendations=["Call mirror_user_intent for the live request, then recommend_next_action"],
    )
    evidence = [{"source": "context", "quote": truncate(inp.context, 80)}] if inp.context else []
    evidence += [{"source": f"memory:{m.ref}", "quote": truncate(m.content, 80)}
                 for m in memory if m.status == "resolved"][:2]
    warnings = ["Request mentioned manipulative tactics; neutral framing enforced"] if manip else []
    return EngineOutput(result, confidence, epistemics, evidence, warnings)
