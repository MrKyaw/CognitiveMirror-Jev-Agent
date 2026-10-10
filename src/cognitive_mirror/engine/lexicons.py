"""Configurable lexicon (JEV-007) and shared signal scoring.

The built-in ``config/jev_dimensions.json`` can be extended or overridden per enterprise by
pointing ``CM_JEV_CONFIG`` at another JSON file. Objects are merged recursively; lists and
scalars in the override replace the default.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from cognitive_mirror.config import CONFIG_DIR
from cognitive_mirror.engine.text import find_phrases, saturate

DEFAULT_PATH = CONFIG_DIR / "jev_dimensions.json"
Lexicon = Mapping[str, Any]


def deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache(maxsize=8)
def load_lexicon(override_path: str | None = None) -> dict[str, Any]:
    lex = json.loads(DEFAULT_PATH.read_text())
    if override_path:
        lex = deep_merge(lex, json.loads(Path(override_path).read_text()))
    return lex


@dataclass(frozen=True)
class Scored:
    name: str
    score: float
    hits: tuple[str, ...]


def score_dimension(text: str, mapping: Mapping[str, list[str]], *,
                    weights: Mapping[str, float] | None = None,
                    negation_aware: bool = True) -> list[Scored]:
    """Score each named dimension by phrase hits in normalized ``text``; best first.

    Ties keep the mapping's order so results are deterministic.
    """
    scored = []
    for name, phrases in mapping.items():
        hits = find_phrases(text, phrases, negation_aware=negation_aware)
        if hits:
            weight = (weights or {}).get(name, 1.0)
            scored.append(Scored(name, min(1.0, saturate(len(hits) * weight)), tuple(hits)))
    order = {name: i for i, name in enumerate(mapping)}
    return sorted(scored, key=lambda s: (-s.score, order[s.name]))


def best(text: str, mapping: Mapping[str, list[str]], **kw: Any) -> Scored | None:
    scored = score_dimension(text, mapping, **kw)
    return scored[0] if scored else None
