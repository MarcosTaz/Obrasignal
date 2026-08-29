from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from .engine import RecoveryCase
from .state import AssistedCaseState


@dataclass(frozen=True)
class TemporalAssessment:
    assessment_date: date
    effective_case: RecoveryCase
    deadline_expired_by_date: bool


def assess_temporal_state(
    state: AssistedCaseState,
    *,
    as_of_date: date | None = None,
) -> TemporalAssessment:
    """Derive time-sensitive notice truth without mutating persisted source state.

    A verified absolute deadline is authoritative for the narrow temporal fact
    that the window has elapsed. Unverified/unknown notice windows remain under
    the engine's existing fail-closed UNKNOWN semantics; this helper never turns
    an uncertain deadline into an expiry fact.
    """

    assessment_date = as_of_date or date.today()
    if not isinstance(assessment_date, date):
        raise ValueError("as_of_date must be a date")

    recovery_case = state.recovery_case
    expired = False
    if state.deadline is not None and recovery_case.notice_window_verified is True:
        deadline = date.fromisoformat(state.deadline)
        if deadline < assessment_date:
            expired = True
            if recovery_case.notice_valid is not False:
                recovery_case = replace(recovery_case, notice_valid=False)

    return TemporalAssessment(
        assessment_date=assessment_date,
        effective_case=recovery_case,
        deadline_expired_by_date=expired,
    )
