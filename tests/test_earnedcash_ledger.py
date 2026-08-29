from decimal import Decimal

import pytest

from earnedcash.ledger import LedgerKind, LedgerRecord, Severity, reconcile_ledger


def record(rid, kind, amount, *, relates_to=None, tenant="t1", customer="c1",
           project="p1", currency="GBP", verified=True, due=None):
    return LedgerRecord(
        record_id=rid,
        tenant_id=tenant,
        customer_id=customer,
        project_id=project,
        currency=currency,
        kind=kind,
        amount=Decimal(amount),
        relates_to=relates_to,
        verified=verified,
        due=due,
    )


def chain(invoice_amount="100", *, due=True):
    return (
        record("app1", LedgerKind.APPLICATION, "100"),
        record("cert1", LedgerKind.CERTIFICATE, "100", relates_to="app1"),
        record("inv1", LedgerKind.INVOICE, invoice_amount, relates_to="cert1", due=due),
    )


def test_verified_due_invoice_surfaces_due_unpaid():
    result = reconcile_ledger(chain())
    assert result.due_unpaid == Decimal("100")
    assert result.verified_cash == Decimal("0")
    assert result.unknown_value == Decimal("0")


def test_not_yet_due_is_not_recovery():
    result = reconcile_ledger(chain(due=False))
    assert result.due_unpaid == Decimal("0")
    assert result.not_yet_due == Decimal("100")


def test_payment_requires_verified_record_for_verified_cash():
    records = chain() + (
        record("pay1", LedgerKind.PAYMENT, "40", relates_to="inv1", verified=False),
    )
    result = reconcile_ledger(records)
    assert result.verified_cash == Decimal("0")
    assert result.due_unpaid == Decimal("60")


def test_verified_partial_payment_reduces_open_and_counts_cash():
    records = chain() + (
        record("pay1", LedgerKind.PAYMENT, "40", relates_to="inv1", verified=True),
    )
    result = reconcile_ledger(records)
    assert result.verified_cash == Decimal("40")
    assert result.due_unpaid == Decimal("60")


def test_cross_tenant_reference_is_p0_and_excluded():
    records = (
        record("app1", LedgerKind.APPLICATION, "100", tenant="t1"),
        record("cert1", LedgerKind.CERTIFICATE, "100", relates_to="app1", tenant="t2"),
        record("inv1", LedgerKind.INVOICE, "100", relates_to="cert1", tenant="t2", due=True),
    )
    result = reconcile_ledger(records)
    assert result.p0_count == 1
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("100")


def test_cross_project_payment_is_not_matched():
    records = chain() + (
        record(
            "pay1",
            LedgerKind.PAYMENT,
            "40",
            relates_to="inv1",
            project="other-project",
        ),
    )
    result = reconcile_ledger(records)
    assert any(a.code == "CROSS_SCOPE_REFERENCE" for a in result.anomalies)
    assert result.verified_cash == Decimal("0")
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("100")


def test_duplicate_record_id_is_p1():
    records = chain() + (
        record("inv1", LedgerKind.PAYMENT, "10", relates_to="inv1"),
    )
    result = reconcile_ledger(records)
    assert any(
        a.code == "DUPLICATE_RECORD_ID" and a.severity == Severity.P1
        for a in result.anomalies
    )


def test_overmatched_invoice_fails_closed():
    records = chain() + (
        record("pay1", LedgerKind.PAYMENT, "90", relates_to="inv1"),
        record("pay2", LedgerKind.PAYMENT, "20", relates_to="inv1"),
    )
    result = reconcile_ledger(records)
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("100")
    assert any(a.code == "OVERMATCHED_INVOICE" for a in result.anomalies)


def test_unverified_evidence_chain_does_not_create_recoverable_value():
    records = (
        record("app1", LedgerKind.APPLICATION, "100", verified=False),
        record("cert1", LedgerKind.CERTIFICATE, "100", relates_to="app1"),
        record("inv1", LedgerKind.INVOICE, "100", relates_to="cert1", due=True),
    )
    result = reconcile_ledger(records)
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("100")


def test_credit_and_deduction_reduce_open_balance_without_counting_as_cash():
    records = chain() + (
        record("credit1", LedgerKind.CREDIT, "10", relates_to="inv1"),
        record("ded1", LedgerKind.DEDUCTION, "5", relates_to="inv1"),
    )
    result = reconcile_ledger(records)
    assert result.verified_cash == Decimal("0")
    assert result.due_unpaid == Decimal("85")


def test_unknown_due_date_fails_closed():
    result = reconcile_ledger(chain(due=None))
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("100")


def test_independent_multiple_tenants_fail_closed_as_p0():
    tenant_two = (
        record("app2", LedgerKind.APPLICATION, "50", tenant="t2"),
        record("cert2", LedgerKind.CERTIFICATE, "50", relates_to="app2", tenant="t2"),
        record("inv2", LedgerKind.INVOICE, "50", relates_to="cert2", tenant="t2", due=True),
    )
    result = reconcile_ledger(chain() + tenant_two)
    assert result.p0_count == 1
    assert any(a.code == "MULTI_TENANT_DATASET" for a in result.anomalies)
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("150")


def test_multiple_currencies_are_never_summed():
    euro = (
        record("app2", LedgerKind.APPLICATION, "50", currency="EUR"),
        record("cert2", LedgerKind.CERTIFICATE, "50", relates_to="app2", currency="EUR"),
        record("inv2", LedgerKind.INVOICE, "50", relates_to="cert2", currency="EUR", due=True),
    )
    result = reconcile_ledger(chain() + euro)
    assert any(
        a.code == "MULTI_CURRENCY_DATASET" and a.severity == Severity.P1
        for a in result.anomalies
    )
    assert result.verified_cash == Decimal("0")
    assert result.due_unpaid == Decimal("0")
    assert result.unknown_value == Decimal("150")


def test_non_finite_amount_is_rejected_at_ledger_boundary():
    with pytest.raises(ValueError, match="invalid amount"):
        reconcile_ledger((record("a1", LedgerKind.APPLICATION, "NaN"),))
