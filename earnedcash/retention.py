from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


class RetentionState(str, Enum):
    NOT_YET_DUE = "NOT_YET_DUE"
    DEFECTS_BLOCKED = "DEFECTS_BLOCKED"
    CLOSEOUT_BLOCKED = "CLOSEOUT_BLOCKED"
    MATURED_EVIDENCE_SUPPORTED = "MATURED_EVIDENCE_SUPPORTED"
    UNKNOWN = "UNKNOWN"
    RELEASED = "RELEASED"


@dataclass(frozen=True)
class RetentionInput:
    tenant_id: str
    project_id: str
    currency: str
    amount_withheld: Decimal
    amount_released: Decimal = ZERO
    release_due: bool | None = None
    valid_defects_open: bool | None = None
    closeout_complete: bool | None = None
    release_condition_evidence_verified: bool = False
    payment_evidence_verified: bool = False


@dataclass(frozen=True)
class RetentionResult:
    state: RetentionState
    held_balance: Decimal
    potentially_recoverable: Decimal
    verified_released_cash: Decimal
    blocker: str | None
    reason: str


def evaluate_retention(item: RetentionInput) -> RetentionResult:
    if item.amount_withheld < ZERO or item.amount_released < ZERO:
        raise ValueError("retention amounts cannot be negative")
    if item.amount_released > item.amount_withheld:
        return RetentionResult(
            state=RetentionState.UNKNOWN,
            held_balance=item.amount_withheld,
            potentially_recoverable=ZERO,
            verified_released_cash=ZERO,
            blocker="AMOUNT_INCONSISTENCY",
            reason="released amount exceeds withheld amount",
        )

    held = item.amount_withheld - item.amount_released
    verified_cash = (
        item.amount_released
        if item.amount_released > ZERO and item.payment_evidence_verified
        else ZERO
    )

    if held == ZERO:
        state = (
            RetentionState.RELEASED
            if item.amount_released == ZERO or item.payment_evidence_verified
            else RetentionState.UNKNOWN
        )
        return RetentionResult(
            state=state,
            held_balance=ZERO,
            potentially_recoverable=ZERO,
            verified_released_cash=verified_cash,
            blocker=None if state == RetentionState.RELEASED else "PAYMENT_EVIDENCE_MISSING",
            reason="no retention balance remains"
            if state == RetentionState.RELEASED
            else "release stated but cash evidence missing",
        )

    if item.release_due is False:
        return RetentionResult(
            RetentionState.NOT_YET_DUE,
            held,
            ZERO,
            verified_cash,
            "NOT_DUE",
            "release condition is explicitly not yet due",
        )
    if item.release_due is None:
        return RetentionResult(
            RetentionState.UNKNOWN,
            held,
            ZERO,
            verified_cash,
            "RELEASE_DUE_UNKNOWN",
            "release timing is not proven",
        )
    if item.valid_defects_open is True:
        return RetentionResult(
            RetentionState.DEFECTS_BLOCKED,
            held,
            ZERO,
            verified_cash,
            "VALID_DEFECT",
            "verified valid defects remain open",
        )
    if item.valid_defects_open is None:
        return RetentionResult(
            RetentionState.UNKNOWN,
            held,
            ZERO,
            verified_cash,
            "DEFECT_STATE_UNKNOWN",
            "defect status is not proven",
        )
    if item.closeout_complete is False:
        return RetentionResult(
            RetentionState.CLOSEOUT_BLOCKED,
            held,
            ZERO,
            verified_cash,
            "CLOSEOUT_DOCUMENT_MISSING",
            "closeout is explicitly incomplete",
        )
    if item.closeout_complete is None:
        return RetentionResult(
            RetentionState.UNKNOWN,
            held,
            ZERO,
            verified_cash,
            "CLOSEOUT_STATE_UNKNOWN",
            "closeout completion is not proven",
        )
    if not item.release_condition_evidence_verified:
        return RetentionResult(
            RetentionState.UNKNOWN,
            held,
            ZERO,
            verified_cash,
            "EVIDENCE_MISSING",
            "maturity conditions are stated but not independently evidenced",
        )

    return RetentionResult(
        RetentionState.MATURED_EVIDENCE_SUPPORTED,
        held,
        held,
        verified_cash,
        None,
        "release due, no valid defects, closeout complete, and conditions evidenced",
    )
