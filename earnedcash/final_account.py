from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


class FinalAccountState(str, Enum):
    PENDING = "PENDING"
    DISPUTED = "DISPUTED"
    AGREED_NOT_DUE = "AGREED_NOT_DUE"
    AGREED_DUE_UNPAID = "AGREED_DUE_UNPAID"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FinalAccountInput:
    tenant_id: str
    project_id: str
    currency: str
    contractor_position: Decimal | None
    customer_position: Decimal | None
    agreed_value: Decimal | None
    invoiced_against_final: Decimal | None
    paid_against_final: Decimal | None
    valid_deductions: Decimal = ZERO
    disputed_value: Decimal = ZERO
    agreement_evidence_verified: bool = False
    invoice_evidence_verified: bool = False
    payment_evidence_verified: bool = False
    payment_due: bool | None = None


@dataclass(frozen=True)
class FinalAccountResult:
    state: FinalAccountState
    agreed_value: Decimal
    open_balance: Decimal
    potentially_recoverable: Decimal
    verified_cash: Decimal
    disputed_value: Decimal
    delta_positions: Decimal | None
    blocker: str | None


def _nn(value: Decimal | None, field: str) -> Decimal | None:
    if value is not None and value < ZERO:
        raise ValueError(f"{field} cannot be negative")
    return value


def evaluate_final_account(item: FinalAccountInput) -> FinalAccountResult:
    contractor = _nn(item.contractor_position, "contractor_position")
    customer = _nn(item.customer_position, "customer_position")
    agreed = _nn(item.agreed_value, "agreed_value")
    invoiced = _nn(item.invoiced_against_final, "invoiced_against_final")
    paid = _nn(item.paid_against_final, "paid_against_final")
    deductions = _nn(item.valid_deductions, "valid_deductions") or ZERO
    disputed = _nn(item.disputed_value, "disputed_value") or ZERO

    delta = contractor - customer if contractor is not None and customer is not None else None

    if agreed is None:
        state = (
            FinalAccountState.DISPUTED
            if disputed > ZERO or (delta not in (None, ZERO))
            else FinalAccountState.PENDING
        )
        return FinalAccountResult(
            state=state,
            agreed_value=ZERO,
            open_balance=ZERO,
            potentially_recoverable=ZERO,
            verified_cash=ZERO,
            disputed_value=disputed,
            delta_positions=delta,
            blocker="FINAL_ACCOUNT_NOT_AGREED",
        )

    if not item.agreement_evidence_verified:
        return FinalAccountResult(
            FinalAccountState.UNKNOWN, agreed, ZERO, ZERO, ZERO, disputed, delta,
            "AGREEMENT_EVIDENCE_MISSING",
        )

    if invoiced is None or paid is None:
        return FinalAccountResult(
            FinalAccountState.UNKNOWN, agreed, ZERO, ZERO, ZERO, disputed, delta,
            "INVOICE_OR_PAYMENT_DATA_MISSING",
        )

    if invoiced > agreed or paid > invoiced:
        return FinalAccountResult(
            FinalAccountState.UNKNOWN, agreed, ZERO, ZERO, ZERO, disputed, delta,
            "AMOUNT_INCONSISTENCY",
        )

    verified_cash = paid if paid == ZERO or item.payment_evidence_verified else ZERO
    net_agreed = max(ZERO, agreed - deductions - disputed)
    open_balance = max(ZERO, net_agreed - paid)

    if open_balance == ZERO:
        state = (
            FinalAccountState.PAID
            if paid == ZERO or item.payment_evidence_verified
            else FinalAccountState.UNKNOWN
        )
        return FinalAccountResult(
            state, agreed, ZERO, ZERO, verified_cash, disputed, delta,
            None if state == FinalAccountState.PAID else "PAYMENT_EVIDENCE_MISSING",
        )

    if not item.invoice_evidence_verified:
        return FinalAccountResult(
            FinalAccountState.UNKNOWN, agreed, open_balance, ZERO, verified_cash,
            disputed, delta, "INVOICE_EVIDENCE_MISSING",
        )

    if item.payment_due is False:
        return FinalAccountResult(
            FinalAccountState.AGREED_NOT_DUE, agreed, open_balance, ZERO,
            verified_cash, disputed, delta, "NOT_DUE",
        )
    if item.payment_due is None:
        return FinalAccountResult(
            FinalAccountState.UNKNOWN, agreed, open_balance, ZERO, verified_cash,
            disputed, delta, "DUE_DATE_UNKNOWN",
        )

    return FinalAccountResult(
        FinalAccountState.AGREED_DUE_UNPAID, agreed, open_balance, open_balance,
        verified_cash, disputed, delta, None,
    )
