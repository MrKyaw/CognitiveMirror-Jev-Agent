"""Optional LLM enricher. Off by default (CM_LLM_PROVIDER=none)."""
from __future__ import annotations

from typing import Any

from cognitive_mirror.config import Settings


def enrich(tool: str, result: dict[str, Any], settings: Settings) -> tuple[bool, list[str]]:
    """Return (enriched, warnings). Deterministic-off path returns False with no warnings."""
    if not settings.llm_enabled:
        return False, []
    if not settings.llm_model:
        return False, ["LLM model not configured; deterministic result returned"]
    return False, ["LLM provider configured but offline MVP keeps deterministic result"]
