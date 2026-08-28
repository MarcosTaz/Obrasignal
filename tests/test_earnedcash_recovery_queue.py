from decimal import Decimal

from earnedcash.ledger import InvoicePosition, LedgerAnomaly, LedgerResult, Severity
from earnedcash.recovery_queue import build_invoice_recovery_queue


def result(*positions, anomalies=()):
    return LedgerResult(
        positions=tuple(positions),
        anomalies=tuple(anomalies),
        verified_cash=Decimal("0"),
        due_unpaid=sum((p.due_unpaid for p in positions), Decimal("0")),
        not_yet_due=sum((p.not_yet_due for p in positions), Decimal("0")),
        unknown_value=sum((p.open_balance for p in positions if p.unknown), Decimal("0")),
    )


def position(invoice_id, amount, *, due_unpaid="0", not_yet_due="0", unknown=False, chain=("app","cert","inv")):
    amount_d = Decimal(amount)
    due_d = Decimal(due_unpaid)
    not_due_d = Decimal(not_yet_due)
    return InvoicePosition(
        invoice_id=invoice_id,
        amount=amount_d,
        verified_cash=Decimal("0"),
        open_balance=max(due_d, not_due_d),
        due_unpaid=due_d,
        not_yet_due=not_due_d,
        unknown=unknown,
        evidence_chain=tuple(chain),
    )


def test_due_supported_invoice_enters_queue():
    queue = build_invoice_recovery_queue(
        result(position("inv1", "25000", due_unpaid="25000")), currency="GBP"
    )
    assert len(queue) == 1
    assert queue[0].amount == Decimal("25000")
    assert queue[0].confidence == "HIGH"


def test_not_yet_due_never_enters_queue():
    queue = build_invoice_recovery_queue(
        result(position("inv1", "25000", not_yet_due="25000")), currency="GBP"
    )
    assert queue == ()


def test_unknown_never_enters_queue():
    queue = build_invoice_recovery_queue(
        result(position("inv1", "25000", due_unpaid="25000", unknown=True)), currency="GBP"
    )
    assert queue == ()


def test_incomplete_evidence_chain_never_enters_queue():
    queue = build_invoice_recovery_queue(
        result(position("inv1", "25000", due_unpaid="25000", chain=("inv1",))), currency="GBP"
    )
    assert queue == ()


def test_any_p0_contamination_suppresses_queue():
    anomaly = LedgerAnomaly(
        code="CROSS_TENANT_REFERENCE",
        severity=Severity.P0,
        record_id="x",
        related_record_id="y",
        detail="cross tenant",
    )
    queue = build_invoice_recovery_queue(
        result(position("inv1", "25000", due_unpaid="25000"), anomalies=(anomaly,)),
        currency="GBP",
    )
    assert queue == ()


def test_queue_is_value_prioritized_deterministically():
    queue = build_invoice_recovery_queue(
        result(
            position("small", "5000", due_unpaid="5000"),
            position("large", "120000", due_unpaid="120000"),
            position("medium", "50000", due_unpaid="50000"),
        ),
        currency="GBP",
    )
    assert [item.case_id for item in queue] == [
        "invoice:large", "invoice:medium", "invoice:small"
    ]
