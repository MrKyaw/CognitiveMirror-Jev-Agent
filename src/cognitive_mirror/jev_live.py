"""Optional live System One / Jev cross-check for ``build_jev_profile`` (PRD 7.3).

The deterministic offline engine always runs first. When ``TYPESAFE_API_KEY`` is set
(and ``typesafe-sdk`` is importable), one System One fan-out call cross-checks the
journey stage and user-confidence signals against the live ``jev`` model.

Any failure (missing key, missing SDK, network, auth) falls back to the
deterministic result with a warning — a ``build_jev_profile`` call never fails
because live Jev is unavailable.
"""
from __future__ import annotations

from typing import Any

from cognitive_mirror.config import Settings

# Jev is priced on input tokens only; output tokens are free ($0.042 / Mtok).
JEV_INPUT_PRICE_PER_TOKEN = 0.042 / 1e6

JEV_STAGES = ("exploring", "deciding", "executing", "following_up", "recovering")


def _choice_stage(answer: Any) -> tuple[str | None, float]:
    choice = getattr(answer, "choice", None)
    conf = getattr(answer, "confidence", 0.0) or 0.0
    if choice in JEV_STAGES:
        return choice, float(conf)
    return None, 0.0


def _noul_p(answer: Any) -> float | None:
    p = getattr(answer, "noul", None)
    return float(p) if p is not None else None


def apply_jev_live(parsed: Any, result: dict[str, Any], evidence: list[dict[str, str]],
                   warnings: list[str], settings: Settings) -> bool:
    """Cross-check a deterministic Jev profile against the live model in place.

    Mutates ``result``/``evidence``/``warnings``. Returns True when the live call
    contributed (envelope engine mode becomes ``hybrid``), False when the
    deterministic result stands alone.
    """
    if not settings.typesafe_api_key:
        return False
    try:
        from typesafe_sdk import Choice, Noul, TypeSafeClient
    except ImportError:
        warnings.append("typesafe-sdk is not installed; deterministic Jev result kept")
        return False
    state = {"context": parsed.context,
             "known_preferences": dict(parsed.known_preferences),
             "recent_interactions": list(parsed.recent_interactions)}
    questions = {
        "journey": Choice(
            instructions="Which journey stage best fits the user's situation?",
            criteria={stage: stage.replace("_", " ") for stage in JEV_STAGES}),
        "user_confident": Noul(
            instructions="The user sounds confident and positive about next steps."),
    }
    try:
        response = TypeSafeClient(api_key=settings.typesafe_api_key).system_one(
            state, questions, model=settings.jev_model)
    except Exception as exc:  # noqa: BLE001 - any live failure falls back
        warnings.append(f"Live Jev unavailable ({exc}); deterministic Jev result kept")
        return False
    answers = getattr(response, "answers", {}) or {}
    usage = getattr(response, "usage", None)
    stage, stage_conf = _choice_stage(answers.get("journey"))
    conf_p = _noul_p(answers.get("user_confident"))
    base = result["journey_stage"]
    if stage is not None and stage_conf >= 0.6 and stage != base["stage"]:
        old = base["stage"]
        result["journey_stage"] = {"stage": stage, "confidence": round(stage_conf, 3),
                                   "evidence": ["jev-live fan-out"]}
        warnings.append(f"Live Jev ({settings.jev_model}) moved journey stage "
                        f"{old} -> {stage}")
    else:
        evidence.append({"source": "jev-live",
                         "quote": f"journey {base['stage']} confirmed"})
    if conf_p is not None:
        decisiveness = abs(2.0 * conf_p - 1.0)
        result["confidence"] = round((result["confidence"] + decisiveness) / 2.0, 3)
    tokens = getattr(usage, "input_tokens", 0) or 0
    cost = tokens * JEV_INPUT_PRICE_PER_TOKEN
    warnings.append(f"Live Jev {settings.jev_model} cross-check applied "
                    f"({tokens} input tokens, ${cost:.6f})")
    evidence.append({"source": "jev-live", "quote": f"model {settings.jev_model}"})
    return True
