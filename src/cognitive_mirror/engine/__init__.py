"""Deterministic cognitive and Jev engine. Every function here is pure and offline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cognitive_mirror.models import Epistemics


@dataclass
class ResolvedMemory:
    """A memory reference as resolved by the service layer before the engine runs."""
    ref: str
    status: str  # resolved | missing | expired | out_of_scope
    content: str = ""
    confidence: float = 0.0
    age_days: float | None = None

    def use(self) -> dict[str, Any]:
        return {"ref": self.ref, "status": self.status, "confidence": self.confidence,
                "age_days": self.age_days}


@dataclass
class EngineOutput:
    result: dict[str, Any]
    confidence: float
    epistemics: Epistemics = field(default_factory=Epistemics)
    evidence: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    policy_decision: dict[str, Any] | None = None


def memory_coverage(memory: list[ResolvedMemory]) -> float | None:
    """Mean confidence across requested refs (missing refs count as 0); None if none asked."""
    if not memory:
        return None
    return round(sum(m.confidence if m.status == "resolved" else 0.0 for m in memory)
                 / len(memory), 3)
