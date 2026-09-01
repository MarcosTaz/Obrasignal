from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TriState(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class ProspectStage(str, Enum):
    PRE_DECISION = "pre_decision"
    RENEWAL_OPEN = "renewal_open"
    IN_PROGRESS = "in_progress"
    RECENT_DECISION = "recent_decision"
    COMPLETED = "completed"


class Challengeability(str, Enum):
    EXPLICIT_ALTERNATIVES = "explicit_alternatives"
    STRUCTURE_UNDER_REVIEW = "structure_under_review"
    MECHANICAL_RENEWAL = "mechanical_renewal"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProspectEvidence:
    organization: str
    stage: ProspectStage
    decision_within_12_months: TriState = TriState.UNKNOWN
    material_estate: TriState = TriState.UNKNOWN
    multiple_credible_alternatives: TriState = TriState.UNKNOWN
    original_business_case_preserved: TriState = TriState.UNKNOWN
    billing_baseline_accessible: TriState = TriState.UNKNOWN
    telemetry_estate_evidence_accessible: TriState = TriState.UNKNOWN
    willing_to_freeze_forecast: TriState = TriState.UNKNOWN
    finops_finance_involved: TriState = TriState.UNKNOWN
    challengeability: Challengeability = Challengeability.UNKNOWN

    def validate(self) -> None:
        if not self.organization.strip():
            raise ValueError("organization is required")
        if self.stage in {ProspectStage.COMPLETED, ProspectStage.RECENT_DECISION} and self.willing_to_freeze_forecast is TriState.YES:
            raise ValueError("completed/recent-decision public records cannot prove willingness to freeze a forecast prospectively")


@dataclass(frozen=True)
class ProspectQualification:
    score: int
    tier: str
    challengeability_overlay: int
    research_priority: int
    unknown_fields: tuple[str, ...]


_WEIGHTS = {
    "decision_within_12_months": 20,
    "material_estate": 15,
    "multiple_credible_alternatives": 15,
    "original_business_case_preserved": 15,
    "billing_baseline_accessible": 10,
    "telemetry_estate_evidence_accessible": 10,
    "willing_to_freeze_forecast": 10,
    "finops_finance_involved": 5,
}

_CHALLENGEABILITY = {
    Challengeability.EXPLICIT_ALTERNATIVES: 15,
    Challengeability.STRUCTURE_UNDER_REVIEW: 10,
    Challengeability.MECHANICAL_RENEWAL: 0,
    Challengeability.UNKNOWN: 0,
}


def qualify(prospect: ProspectEvidence) -> ProspectQualification:
    prospect.validate()
    score = 0
    unknown = []
    for field, weight in _WEIGHTS.items():
        state = getattr(prospect, field)
        if state is TriState.YES:
            score += weight
        elif state is TriState.UNKNOWN:
            unknown.append(field)

    tier = "A" if score >= 70 else "B" if score >= 50 else "HOLD"
    overlay = _CHALLENGEABILITY[prospect.challengeability]

    # Research priority is deliberately not the canonical qualification score.
    # It helps choose what to investigate next without pretending missing buyer
    # evidence has been validated. Completed/recent decisions are capped because
    # the original forecast can no longer be frozen prospectively.
    research_priority = score + overlay
    if prospect.stage is ProspectStage.IN_PROGRESS:
        research_priority = min(research_priority, 75)
    elif prospect.stage in {ProspectStage.RECENT_DECISION, ProspectStage.COMPLETED}:
        research_priority = min(research_priority, 35)

    return ProspectQualification(
        score=score,
        tier=tier,
        challengeability_overlay=overlay,
        research_priority=research_priority,
        unknown_fields=tuple(unknown),
    )
