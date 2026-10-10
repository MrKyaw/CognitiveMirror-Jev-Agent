"""mirror_user_intent (PRD 8.1, COG-001..008)."""
from __future__ import annotations

import re
from typing import Any

from cognitive_mirror.engine import EngineOutput, ResolvedMemory, memory_coverage
from cognitive_mirror.engine.lexicons import Lexicon, Scored, best, score_dimension
from cognitive_mirror.engine.text import (
    capitalize_first,
    clip,
    find_deadline,
    find_phrases,
    is_same_day,
    lower_first,
    normalize,
    saturate,
    second_person,
    sentences,
    snippet,
    truncate,
    words,
)
from cognitive_mirror.models import Epistemics, MirrorUserIntentInput

GENERAL = "general_assistance"
URGENCY_SCORES = {"critical": 0.95, "high": 0.75, "medium": 0.5, "low": 0.15}
URGENCY_ORDER = ("low", "medium", "high", "critical")
NEGATIVE_EMOTIONS = ("frustration", "concern", "disappointment")
CRISIS_TERMS = (
    "kill myself", "suicide", "suicidal", "end my life", "hurt myself", "self-harm",
    "self harm", "want to die", "hurt someone", "kill someone",
)

_VAGUE_REF = re.compile(
    r"\b(?:fix|send|update|review|finish|do|handle|change|improve|summari[sz]e|reply to|"
    r"forward|redo|check|edit)\s+(?:it|this|that|them|those|these)\b")
_RECIPIENT_WORDS = (
    "manager", "boss", "recruiter", "client", "customer", "team", "colleague", "hiring manager",
    "ceo", "cto", "investor", "landlord", "professor", "candidate", "vendor", "partner",
    "stakeholders", "board", "hr", "friend", "coworker", "lead", "director",
)
_RECIPIENT_RE = re.compile(r"\b(?:to|for|with)\s+(?:my|the|our|his|her|their|a|an)\s+[a-z]+"
                           r"|\b(?:to|for|with)\s+[A-Z][a-z]+")
_OPTION_RE = re.compile(r"\bor\b|\bbetween\b|\bvs\.?\b|\bversus\b|\boptions?\b")
_TIME_RE = re.compile(r"\b(?:\d{1,2}(?::\d{2})?\s?(?:am|pm)|morning|afternoon|evening|"
                      r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|"
                      r"tomorrow|next week|this week|\d{1,2}/\d{1,2})\b")
_DECIDE_Q = re.compile(r"^(?:should|shall|do|can|could)\s+(?:i|we)\s+(.+)", re.IGNORECASE)
_VAGUE_SUCCESS = ("better", "improve", "optimize", "optimise", "more effective", "best",
                  "nicer", "stronger")
_PREFERENCE_RE = re.compile(r"\b(?:i|we)\s+(?:prefer|like|usually|always|hate|don't like|"
                            r"do not like|tend to)\b[^.!?\n]*")
_FORMATS = (
    ("bullet", "bullet list"), ("table", "table"), ("slides", "slide outline"),
    ("deck", "slide outline"), ("one-pager", "one-page brief"), ("one pager", "one-page brief"),
    ("checklist", "checklist"), ("email", "email"), ("outline", "outline"),
)
_CONSTRAINT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("policy", re.compile(r"\b(?:confidential|nda|gdpr|hipaa|pipeda|compliance|compliant|"
                          r"policy|approved by legal|legal review|internal only)\b")),
    ("budget", re.compile(r"(?:[$\u20ac\u00a3]\s?\d|\b\d[\d,.]*\s?(?:k|m)?\s?(?:usd|cad|eur|"
                          r"dollars)\b|\bbudget\b|\bcost under\b|\bfree\b)")),
    ("time", re.compile(r"\b(?:deadline|due|by (?:eod|end of|tomorrow|today|tonight|monday|"
                        r"tuesday|wednesday|thursday|friday)|within \d+|in \d+ (?:hours?|days?)|"
                        r"before (?:the|my|our|\d))")),
    ("format", re.compile(r"\b(?:under|max(?:imum)?|at most|less than|no more than)?\s*\d+\s+"
                          r"(?:words|pages?|slides|bullets|sentences|minutes)\b|\bone[- ]page"
                          r"\b|\bbullet points?\b|\bin a table\b|\bparagraphs?\b")),
    ("scope", re.compile(r"\b(?:only|must not|do not|don't|without|no more than|avoid|"
                         r"exclude|except|limit(?:ed)? to|focus on)\b")),
    ("quality", re.compile(r"\b(?:must be|needs? to be|should be|has to be|professional|"
                           r"accurate|error-free|polished)\b")),
    ("resource", re.compile(r"\b(?:only have|by myself|alone|no team|one person|limited "
                            r"(?:time|resources|staff)|small team)\b")),
)


# --------------------------------------------------------------------------- helpers

def extract_goals(text: str, lex: Lexicon, limit: int = 5, fallback: bool = False) -> list[str]:
    """Explicit goal clauses: text after goal markers, or imperative sentences.

    With ``fallback`` and no marker found, the first sentence becomes the goal
    ("Should we X?" becomes "Decide whether to X").
    """
    goals: list[str] = []
    markers = sorted(lex["goal_markers"], key=len, reverse=True)
    verbs = set(lex["imperative_verbs"])
    for sent in sentences(text):
        flat = " ".join(sent.split())
        low = normalize(flat)
        goal = None
        for marker in markers:
            idx = low.find(marker)
            if idx >= 0 and (idx == 0 or not low[idx - 1].isalnum()):
                goal = flat[idx + len(marker):]
                break
        else:
            first = words(sent)[:1]
            if first and first[0] in verbs:
                goal = sent
        if goal:
            goal = re.sub(r"^(?:please|me|us|to)\s+", "", goal.strip(" ,:;-"), flags=re.IGNORECASE)
            goal = goal.strip().rstrip(".!?").strip()
            if len(goal.split()) >= 2 and goal.lower() not in (g.lower() for g in goals):
                goals.append(truncate(capitalize_first(goal), 200))
        if len(goals) >= limit:
            break
    if not goals and fallback:
        first = next(iter(sentences(text)), "")
        decide = _DECIDE_Q.match(" ".join(first.split()))
        if decide:
            goals.append(truncate("Decide whether to " + decide.group(1).rstrip("?. "), 200))
        elif len(words(first)) >= 3:
            goals.append(truncate(capitalize_first(first.rstrip("?.! ")), 200))
    return goals


def extract_constraints(text: str, limit: int = 8) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for sent in sentences(text):
        low = normalize(sent)
        for ctype, pattern in _CONSTRAINT_RULES:
            if pattern.search(low) and (ctype, low) not in seen:
                seen.add((ctype, low))
                out.append({"type": ctype, "text": truncate(sent.strip(), 200)})
                break
        if len(out) >= limit:
            break
    return out


def detect_urgency(text: str, lex: Lexicon, original: str) -> dict[str, Any]:
    level, signals = None, []
    for name in ("critical", "high", "medium", "low"):
        hits = find_phrases(text, lex["urgency"][name], negation_aware=True)
        if hits:
            level, signals = name, hits
            break
    deadline = find_deadline(original)
    if deadline:
        floor = "high" if is_same_day(deadline) else "medium"
        if level is None or URGENCY_ORDER.index(level) < URGENCY_ORDER.index(floor):
            level = floor
        signals = [*signals, deadline]
    if level is None:
        return {"level": "medium", "score": 0.4, "signals": [], "deadline_text": None,
                "assumed": True}
    return {"level": level, "score": URGENCY_SCORES[level], "signals": signals,
            "deadline_text": deadline, "assumed": False}


def classify(msg: str, ctx: str, agent_goal: str, lex: Lexicon) -> list[Scored]:
    scored: list[Scored] = []
    order = list(lex["intents"])
    for name, spec in lex["intents"].items():
        hits = find_phrases(msg, spec["keywords"])
        ctx_hits = find_phrases(ctx, spec["keywords"]) if ctx else []
        goal_hit = bool(agent_goal) and bool(find_phrases(agent_goal, spec["keywords"]))
        score = saturate(len(hits)) + 0.3 * saturate(len(ctx_hits)) + (0.2 if goal_hit else 0)
        if score > 0:
            scored.append(Scored(name, clip(score), tuple(hits or ctx_hits)))
    scored.sort(key=lambda s: (-s.score, order.index(s.name)))
    if not scored:
        is_question = msg.rstrip().endswith("?") or msg.split(" ", 1)[0] in (
            "what", "why", "how", "who", "when", "where", "which", "is", "are", "can", "does")
        if is_question:
            return [Scored("learn_explain", 0.35, ())]
        return [Scored(GENERAL, 0.2, ())]
    return scored


# --------------------------------------------------------------------------- main

def mirror_user_intent(inp: MirrorUserIntentInput, memory: list[ResolvedMemory],
                       lex: Lexicon) -> EngineOutput:
    original = inp.user_message
    msg = normalize(original)
    ctx = normalize(" ".join(inp.conversation_context[-10:]))
    goal_txt = normalize(inp.agent_goal or "")
    mem_text = normalize(" ".join(m.content for m in memory if m.status == "resolved"))
    all_text = " ".join(t for t in (msg, ctx, mem_text) if t)

    intents = classify(msg, ctx, goal_txt, lex)
    primary = intents[0]
    secondary = [s for s in intents[1:] if s.score >= 0.3 and s.score >= 0.5 * primary.score][:3]
    spec = lex["intents"].get(primary.name, {})

    explicit_goals = extract_goals(original, lex, fallback=primary.name != GENERAL)
    constraints = extract_constraints(original + "\n" + "\n".join(inp.conversation_context[-3:]))
    urgency = detect_urgency(msg, lex, original)
    emotions = score_dimension(msg, lex["emotions"])
    values = score_dimension(all_text, lex["value_drivers"], weights=lex["value_weights"])
    style = best(all_text, lex["decision_style"])
    tone = best(all_text, lex["communication"])
    risk = best(all_text, lex["risk_tolerance"])
    crisis = find_phrases(msg, CRISIS_TERMS)

    implicit_goals = list(spec.get("implicit_goals", ["Get a useful, accurate answer quickly"]))
    if urgency["level"] in ("high", "critical"):
        implicit_goals.append("Finish quickly without sacrificing what matters most")
    if any(e.name in NEGATIVE_EMOTIONS and e.score >= 0.4 for e in emotions):
        implicit_goals.append("Reduce stress and regain a sense of control")
    implicit_goals = list(dict.fromkeys(implicit_goals))[:5]

    ambiguities = _ambiguities(original, msg, ctx, primary, secondary, memory)
    conflicts = _conflicts(f"{msg} {ctx}", lex)

    preferred_tone = None
    if tone:
        preferred_tone = tone.name
    elif any(e.name == "frustration" and e.score >= 0.4 for e in emotions):
        preferred_tone = "calm and direct"
    working_prefs = [truncate(capitalize_first(m.group(0).strip()), 160)
                     for m in _PREFERENCE_RE.finditer(f"{msg} {mem_text}")][:5]

    desired = spec.get("desired_output", "helpful, direct answer")
    fmt = next((label for key, label in _FORMATS if find_phrases(msg, [key])), None)
    if fmt and fmt not in desired:
        desired = f"{desired} ({fmt})"

    outcomes = []
    if spec.get("outcome"):
        outcomes.append({"outcome": spec["outcome"][0], "metric": spec["outcome"][1]})
    for v in values[:2]:
        outcome, metric = lex["value_outcomes"].get(v.name, (None, None))
        if outcome:
            outcomes.append({"outcome": outcome, "metric": metric})
    if not outcomes:
        outcomes.append({"outcome": "Task completed with less back-and-forth",
                         "metric": "turns to completion"})

    coverage = memory_coverage(memory)
    blocking = [a for a in ambiguities if a["blocking"]]
    confidence = clip(
        0.25 + 0.45 * primary.score + (0.15 if explicit_goals else 0.0)
        + (0.1 if coverage is None else 0.15 * coverage)
        - 0.2 * len(blocking) - 0.05 * (len(ambiguities) - len(blocking)), 0.05, 0.97)

    strategy = _strategy(primary, spec, blocking, ambiguities, crisis, confidence)
    summary = _mirror_summary(explicit_goals, desired, urgency, values, constraints, emotions,
                              blocking)
    reflection = _reflection(primary, conflicts, emotions, urgency)

    result = {
        "primary_intent": {"label": primary.name, "confidence": primary.score,
                           "evidence": [snippet(original, h) for h in primary.hits[:3]]},
        "secondary_intents": [{"label": s.name, "confidence": s.score,
                               "evidence": [snippet(original, h) for h in s.hits[:2]]}
                              for s in secondary],
        "explicit_goals": explicit_goals,
        "implicit_goals": implicit_goals,
        "constraints": constraints,
        "urgency": {k: urgency[k] for k in ("level", "score", "signals", "deadline_text")},
        "ambiguities": ambiguities,
        "conflicts": conflicts,
        "decision_style": style.name if style else None,
        "preferred_tone": preferred_tone,
        "risk_tolerance": risk.name if risk else "unknown",
        "working_preferences": working_prefs,
        "desired_output": desired,
        "mirror_summary": summary,
        "business_outcomes": outcomes[:3],
        "reflection_prompts": reflection,
        "recommended_agent_response_strategy": strategy,
        "memory_used": [m.use() for m in memory],
        "confidence": confidence,
    }

    assumptions = []
    if urgency["assumed"]:
        assumptions.append("No urgency or deadline stated; assumed normal priority")
    if not inp.conversation_context and not memory:
        assumptions.append("No conversation history or memory provided; using this message only")
    if primary.name == GENERAL:
        assumptions.append("No specific intent recognized; treating as a general request")
    assumptions += [f"Memory {m.ref} is {m.status}; not used" for m in memory
                    if m.status != "resolved"]
    epistemics = Epistemics(
        facts=[f"User stated goal: {g}" for g in explicit_goals[:3]]
        + [f"Stated {c['type']} constraint: {c['text']}" for c in constraints[:3]]
        + ([f"Stated deadline: {urgency['deadline_text']}"] if urgency["deadline_text"] else []),
        assumptions=assumptions,
        inferences=[f"Implicit goal: {g}" for g in implicit_goals[:3]]
        + [f"Emotion signal: {e.name} ({e.score})" for e in emotions[:2]]
        + ([f"Decision style: {style.name}"] if style else []),
        recommendations=[f"{strategy['mode']}: {strategy['rationale']}"],
    )
    evidence = [{"source": "user_message", "quote": snippet(original, h)} for h in primary.hits[:3]]
    evidence += [{"source": "user_message", "quote": s} for s in urgency["signals"][:2]]
    evidence += [{"source": f"memory:{m.ref}", "quote": truncate(m.content, 80)}
                 for m in memory if m.status == "resolved"][:3]
    warnings = []
    if crisis:
        warnings.append("Possible crisis language detected: respond with care and point to "
                        "professional or emergency resources")
    return EngineOutput(result, confidence, epistemics, evidence, warnings)


def _ambiguities(original: str, msg: str, ctx: str, primary: Scored, secondary: list[Scored],
                 memory: list[ResolvedMemory]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n_words = len(words(msg))
    has_context = bool(ctx) or any(m.status == "resolved" for m in memory)

    def add(issue: str, question: str, blocking: bool) -> None:
        out.append({"issue": issue, "clarification_question": question, "blocking": blocking})

    if n_words < 4 and not has_context:
        add("Request is very brief", "Could you share a bit more about what you want to "
            "achieve and what a good result looks like?", True)
    elif primary.name == GENERAL:
        add("Goal is unclear", "What outcome are you hoping for, and what should I produce "
            "(for example a draft, a plan, or a recommendation)?", True)
    if _VAGUE_REF.search(msg) and not has_context:
        add("Unclear reference ('it'/'this') with no prior context",
            "What exactly are you referring to? Please paste or describe it.", n_words < 12)
    if primary.name in ("draft_communication", "follow_up") and not (
            _RECIPIENT_RE.search(original) or find_phrases(msg, _RECIPIENT_WORDS)):
        add("Recipient or audience not specified",
            "Who is this for, and what is your relationship with them?", False)
    if primary.name == "schedule_task" and not _TIME_RE.search(msg):
        add("Timing not specified", "When should this happen, and how long should it be?",
            False)
    if primary.name == "make_decision" and not _OPTION_RE.search(msg):
        add("Options not stated", "Which options are you considering?", False)
    if find_phrases(msg, _VAGUE_SUCCESS) and not re.search(r"\d", msg):
        add("Success criteria are vague", "How will you know it worked? Is there a target or "
            "metric?", False)
    if secondary and secondary[0].score >= 0.9 * primary.score and primary.score >= 0.4:
        add(f"Two requests compete ({primary.name} and {secondary[0].name})",
            f"Should I start with {primary.name.replace('_', ' ')} or "
            f"{secondary[0].name.replace('_', ' ')}?", False)
    missing = [m.ref for m in memory if m.status != "resolved"]
    if missing:
        add(f"{len(missing)} referenced memory item(s) unavailable or expired",
            "Some saved context is unavailable; can you confirm the key details again?", False)
    return out


def _conflicts(text: str, lex: Lexicon) -> list[dict[str, Any]]:
    out = []
    for c in lex["conflicts"]:
        a = find_phrases(text, c["a_terms"], negation_aware=True)
        b = find_phrases(text, c["b_terms"], negation_aware=True)
        if a and b:
            out.append({"between": [c["a"], c["b"]],
                        "description": f"'{a[0]}' suggests {c['a']} while '{b[0]}' suggests "
                                       f"{c['b']}",
                        "resolution_hint": c["hint"]})
    return out


def _strategy(primary: Scored, spec: dict[str, Any], blocking: list[dict[str, Any]],
              ambiguities: list[dict[str, Any]], crisis: list[str],
              confidence: float) -> dict[str, Any]:
    if crisis:
        return {"mode": "escalate",
                "rationale": "Message contains possible crisis language; wellbeing comes first",
                "steps": ["Respond with empathy and without judgment",
                          "Share appropriate crisis or emergency resources",
                          "Do not continue the task until the user is safe",
                          "Involve a human if your deployment supports it"]}
    if blocking or confidence < 0.35:
        questions = [a["clarification_question"] for a in (blocking or ambiguities)][:2]
        asks = [f"Ask: {q}" for q in questions] or ["Ask what outcome the user wants"]
        return {"mode": "clarify_first",
                "rationale": "Acting now would likely miss the user's intent; one short "
                             "clarification is cheaper than a wrong answer",
                "steps": [*asks, "Offer a sensible default the user can accept with one word"]}
    if primary.name == "reflect":
        return {"mode": "reflect",
                "rationale": "User is asking for help thinking, not for a deliverable",
                "steps": ["Mirror back the priorities and tensions you heard",
                          "Offer one or two reflection prompts, without prescribing",
                          "Suggest one small, concrete next step the user can choose"]}
    if spec.get("side_effects"):
        return {"mode": "act_with_confirmation",
                "rationale": "The task affects other people or external systems, so the user "
                             "should approve before anything is sent or booked",
                "steps": ["Prepare the draft or proposal",
                          "Call check_guardrails on the planned external action",
                          "Show it to the user and wait for explicit approval",
                          "Execute only after approval and log the outcome"]}
    steps = ["Produce the deliverable directly, leading with the answer"]
    if ambiguities:
        steps.append("State the assumptions you made for the open questions")
    steps.append("Offer one optional refinement")
    return {"mode": "act", "rationale": "Intent is clear enough to act; low external risk",
            "steps": steps}


def _mirror_summary(goals: list[str], desired: str, urgency: dict[str, Any],
                    values: list[Scored], constraints: list[dict[str, str]],
                    emotions: list[Scored], blocking: list[dict[str, Any]]) -> str:
    goal = second_person(lower_first(goals[0])) if goals else f"get a {desired}"
    parts = [f"It sounds like you want to {goal.rstrip('.')}."]
    if urgency["deadline_text"]:
        parts.append(f"Timing matters: {urgency['deadline_text']}.")
    elif not urgency["assumed"]:
        parts.append(f"Urgency looks {urgency['level']}.")
    if values:
        parts.append("What seems to matter most: "
                     + ", ".join(v.name.replace("_", " ") for v in values[:2]) + ".")
    if constraints:
        parts.append("Constraints to respect: " + "; ".join(
            second_person(truncate(c["text"], 70)).rstrip(".!?\u2026") for c in constraints[:2])
            + ".")
    strong = [e for e in emotions if e.score >= 0.4]
    if strong:
        parts.append(f"I'm also noticing some {strong[0].name} in how you described this.")
    if blocking:
        parts.append(f"Before acting, it would help to know: {blocking[0]['clarification_question']}")
    return truncate(" ".join(parts), 700)


def _reflection(primary: Scored, conflicts: list[dict[str, Any]], emotions: list[Scored],
                urgency: dict[str, Any]) -> list[str]:
    prompts = []
    if conflicts:
        a, b = conflicts[0]["between"]
        prompts.append(f"If you could protect only one of {a} or {b} here, which would it be?")
    if primary.name == "make_decision":
        prompts.append("What would you need to see to feel confident in either choice?")
    names = {e.name for e in emotions if e.score >= 0.4}
    if names & {"concern", "frustration"}:
        prompts.append("Which part of this is within your control this week?")
    if "disappointment" in names:
        prompts.append("What is one thing you would keep and one thing you would change "
                       "next time?")
    if urgency["level"] in ("high", "critical"):
        prompts.append("What is the smallest version of this that would still be a win?")
    if not prompts:
        prompts.append("What would a great outcome look like a week from now?")
    return prompts[:3]
