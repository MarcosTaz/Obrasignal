import pytest

from factory_cloud.synthetic_billing import SyntheticBillingError, SyntheticBillingLedger


def test_synthetic_billing_keeps_recovery_and_platform_fee_separate(tmp_path):
    ledger = SyntheticBillingLedger(tmp_path / "billing.sqlite3")
    invoice = ledger.quote(
        tenant_id="synthetic-enterprise", invoice_id="inv-test-1", factory_id="contractcredit",
        engagement_id="eng-1", recovery_amount="5000", fee_percent="20", currency="EUR",
    )
    assert invoice.recovery_amount == "5000.00"
    assert invoice.fee_amount == "1000.00"
    assert invoice.state == "QUOTED_TEST"
    assert invoice.real_revenue is False
    assert ledger.transition(tenant_id=invoice.tenant_id, invoice_id=invoice.invoice_id, target="APPROVED_TEST").state == "APPROVED_TEST"
    assert ledger.transition(tenant_id=invoice.tenant_id, invoice_id=invoice.invoice_id, target="INVOICED_TEST").state == "INVOICED_TEST"
    settled = ledger.transition(tenant_id=invoice.tenant_id, invoice_id=invoice.invoice_id, target="SETTLED_TEST")
    assert settled.state == "SETTLED_TEST"
    assert settled.real_revenue is False


def test_synthetic_billing_cannot_skip_states_or_claim_paid(tmp_path):
    ledger = SyntheticBillingLedger(tmp_path / "billing.sqlite3")
    invoice = ledger.quote(
        tenant_id="t", invoice_id="i", factory_id="aviation-lease-entitlement-recovery",
        engagement_id="e", recovery_amount="75000", fee_percent="15", currency="EUR",
    )
    with pytest.raises(SyntheticBillingError, match="invalid synthetic billing transition"):
        ledger.transition(tenant_id="t", invoice_id="i", target="SETTLED_TEST")
    with pytest.raises(SyntheticBillingError, match="invalid synthetic billing transition"):
        ledger.transition(tenant_id="t", invoice_id="i", target="PAID")
    assert invoice.real_revenue is False


def test_synthetic_billing_is_tenant_scoped_and_engagement_unique(tmp_path):
    ledger = SyntheticBillingLedger(tmp_path / "billing.sqlite3")
    ledger.quote(tenant_id="a", invoice_id="same", factory_id="contractcredit", engagement_id="eng", recovery_amount="100", fee_percent="10", currency="EUR")
    ledger.quote(tenant_id="b", invoice_id="same", factory_id="contractcredit", engagement_id="eng", recovery_amount="100", fee_percent="10", currency="EUR")
    assert ledger.get(tenant_id="a", invoice_id="same").tenant_id == "a"
    assert ledger.get(tenant_id="b", invoice_id="same").tenant_id == "b"
    with pytest.raises(SyntheticBillingError, match="not found"):
        ledger.get(tenant_id="c", invoice_id="same")
    with pytest.raises(SyntheticBillingError, match="duplicate"):
        ledger.quote(tenant_id="a", invoice_id="other", factory_id="contractcredit", engagement_id="eng", recovery_amount="100", fee_percent="10", currency="EUR")


def test_invalid_amounts_and_fees_fail_closed(tmp_path):
    ledger = SyntheticBillingLedger(tmp_path / "billing.sqlite3")
    for recovery, fee in (("-1", "10"), ("NaN", "10"), ("100", "101"), ("100", "-1")):
        with pytest.raises(SyntheticBillingError):
            ledger.quote(
                tenant_id="t", invoice_id=f"i-{recovery}-{fee}", factory_id="contractcredit",
                engagement_id=f"e-{recovery}-{fee}", recovery_amount=recovery, fee_percent=fee, currency="EUR",
            )
