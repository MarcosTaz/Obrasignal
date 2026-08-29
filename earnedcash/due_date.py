from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class DueTruthState(str, Enum):
    DUE = "DUE"
    NOT_YET_DUE = "NOT_YET_DUE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DueDateEvidence:
    due_date: date | None
    evidence_ref: str | None
    independently_verified: bool


@dataclass(frozen=True)
class DueTruthResult:
    state: DueTruthState
    due: bool | None
    as_of: date
    due_date: date | None
    evidence_ref: str | None
    reason: str


def determine_due_truth(*, as_of: date, evidence: DueDateEvidence) -> DueTruthResult:
    """Derive due truth from an explicit observation date and verified evidence.

    No wall-clock/today value is read here. Re-running the same evidence at the
    same `as_of` date is deterministic.
    """
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    if evidence.due_date is not None and not isinstance(evidence.due_date, date):
        raise ValueError("due_date must be a date or null")

    evidence_ref = (evidence.evidence_ref or "").strip() or None
    if not evidence.independently_verified:
        return DueTruthResult(
            DueTruthState.UNKNOWN,
            None,
            as_of,
            evidence.due_date,
            evidence_ref,
            "DUE_DATE_EVIDENCE_NOT_VERIFIED",
        )
    if evidence.due_date is None:
        return DueTruthResult(
            DueTruthState.UNKNOWN,
            None,
            as_of,
            None,
            evidence_ref,
            "DUE_DATE_MISSING",
        )
    if evidence_ref is None:
        return DueTruthResult(
            DueTruthState.UNKNOWN,
            None,
            as_of,
            evidence.due_date,
            None,
            "DUE_DATE_EVIDENCE_REFERENCE_MISSING",
        )

    due = as_of >= evidence.due_date
    return DueTruthResult(
        DueTruthState.DUE if due else DueTruthState.NOT_YET_DUE,
        due,
        as_of,
        evidence.due_date,
        evidence_ref,
        "AS_OF_ON_OR_AFTER_VERIFIED_DUE_DATE"
        if due
        else "AS_OF_BEFORE_VERIFIED_DUE_DATE",
    )
