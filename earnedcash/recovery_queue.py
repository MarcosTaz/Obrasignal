from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .ledger import LedgerResult


ZERO = Decimal("0")


@dataclass(frozen=True)
class RecoveryQueueItem:
    case_id: str
    category: str
    amount: Decimal
    currency: str
    confidence: str
    evidence_quality: str
    blocker: str | None
    action: str
    priority_score: int
    evidence_chain: tuple[str, ...]


def _amount_score(amount: Decimal) -> int:
    if amount >= Decimal("100000"):
        return 50
    if amount >= Decimal("50000"):
        return 40
    if amount >= Decimal("10000"):
        return 30
    if amount > ZERO:
        return 20
    return 0


def build_invoice_recovery_queue(
    result: LedgerResult, *, currency: str
) -> tuple[RecoveryQueueItem, ...]:
    """Build a queue only from evidence-supported due/unpaid invoice positions.

    UNKNOWN, not-yet-due and P0-contaminated positions never become queue items.
    The queue is an analytical action list, not a claim that cash will be collected.
    """
    if result.p0_count:
        return ()

    items: list[RecoveryQueueItem] = []
    for position in result.positions:
        if position.unknown or position.due_unpaid <= ZERO:
            continue
        chain = position.evidence_chain
        evidence_quality = "HIGH" if len(chain) >= 3 else "UNKNOWN"
        if evidence_quality != "HIGH":
            continue
        score = min(100, _amount_score(position.due_unpaid) + 40)
        items.append(
            RecoveryQueueItem(
                case_id=f"invoice:{position.invoice_id}",
                category="INVOICED_DUE_UNPAID",
                amount=position.due_unpaid,
                currency=currency,
                confidence="HIGH",
                evidence_quality=evidence_quality,
                blocker="PAYMENT_DELAY",
                action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
                priority_score=score,
                evidence_chain=chain,
            )
        )

    return tuple(
        sorted(
            items,
            key=lambda item: (
                -item.priority_score,
                -item.amount,
                item.case_id,
            ),
        )
    )
