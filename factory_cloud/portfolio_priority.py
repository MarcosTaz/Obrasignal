from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PortfolioPriorityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrioritySignals:
    safety_severity: int = 0
    pilot_blocker: int = 0
    commercial_leverage: int = 0
    shared_leverage: int = 0
    evidence_integrity: int = 0
    base_priority: int = 0

    @classmethod
    def from_app(cls, app: dict[str, Any]) -> "PrioritySignals":
        activation = app.get("activation") or {}
        raw = app.get("portfolio_priority") or {}
        values = {
            "safety_severity": raw.get("safety_severity", 0),
            "pilot_blocker": raw.get("pilot_blocker", 0),
            "commercial_leverage": raw.get("commercial_leverage", 0),
            "shared_leverage": raw.get("shared_leverage", 0),
            "evidence_integrity": raw.get("evidence_integrity", 0),
            "base_priority": activation.get("priority", 0),
        }
        normalized: dict[str, int] = {}
        for key, value in values.items():
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise PortfolioPriorityError(f"invalid priority signal {key}") from exc
            if key != "base_priority" and not 0 <= number <= 100:
                raise PortfolioPriorityError(f"priority signal out of range {key}: {number}")
            normalized[key] = number
        return cls(**normalized)

    @property
    def score(self) -> int:
        # Strict lexicographic ordering using base-101 digits. One point of a
        # higher-order signal always dominates every possible combination below it:
        # safety > pilot blocker > evidence integrity > commercial > shared > base.
        bounded_base = max(0, min(self.base_priority, 100))
        score = self.safety_severity
        for value in (
            self.pilot_blocker,
            self.evidence_integrity,
            self.commercial_leverage,
            self.shared_leverage,
            bounded_base,
        ):
            score = score * 101 + value
        return score


def priority_for_app(app: dict[str, Any]) -> PrioritySignals:
    return PrioritySignals.from_app(app)
