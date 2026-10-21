from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


class CaseState(str, Enum):
    OPEN = "OPEN"
    ACTION_APPROVED = "ACTION_APPROVED"
    RECOVERY_REQUESTED = "RECOVERY_REQUESTED"
    SETTLED = "SETTLED"
    PAID = "PAID"
    CLOSED_ZERO = "CLOSED_ZERO"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


@dataclass(frozen=True)
class CaseTransition:
    from_state: CaseState
    to_state: CaseState
    reason: str


_ALLOWED = {
    CaseState.OPEN: {CaseState.ACTION_APPROVED, CaseState.CLOSED_ZERO, CaseState.REQUIRES_REVIEW},
    CaseState.ACTION_APPROVED: {CaseState.RECOVERY_REQUESTED, CaseState.REQUIRES_REVIEW},
    CaseState.RECOVERY_REQUESTED: {CaseState.SETTLED, CaseState.PAID, CaseState.REQUIRES_REVIEW},
    CaseState.SETTLED: {CaseState.PAID, CaseState.REQUIRES_REVIEW},
    CaseState.REQUIRES_REVIEW: {CaseState.OPEN, CaseState.CLOSED_ZERO},
    CaseState.PAID: set(),
    CaseState.CLOSED_ZERO: set(),
}


def transition_case(
    *,
    current: CaseState,
    target: CaseState,
    amount: Decimal,
    customer_approved: bool = False,
    settlement_evidence_verified: bool = False,
    cash_evidence_verified: bool = False,
) -> CaseTransition:
    if not amount.is_finite() or amount < ZERO:
        raise ValueError("invalid case amount")
    if target not in _ALLOWED[current]:
        raise ValueError(f"invalid transition: {current.value}->{target.value}")
    if target == CaseState.ACTION_APPROVED and not customer_approved:
        raise ValueError("customer approval required")
    if target == CaseState.RECOVERY_REQUESTED and not customer_approved:
        raise ValueError("customer approval required")
    if target == CaseState.SETTLED and not settlement_evidence_verified:
        raise ValueError("settlement evidence required")
    if target == CaseState.PAID and not cash_evidence_verified:
        raise ValueError("verified cash evidence required")
    if target == CaseState.CLOSED_ZERO and amount != ZERO:
        raise ValueError("non-zero case cannot close as zero")
    return CaseTransition(
        from_state=current,
        to_state=target,
        reason="EVIDENCE_GATED_TRANSITION",
    )
