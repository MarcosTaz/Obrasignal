from decimal import Decimal

import pytest

from factory_cloud.billing_core import BillingStateError, create_revenue_record
from factory_cloud.revenue_ledger import RevenueLedger


def _record(factory_id="warrantyguard", engagement_id="WG-001"):
    return create_revenue_record(
        factory_id=factory_id,
        engagement_id=engagement_id,
        customer_id="synthetic-customer",
        recovery_amount="400000",
        platform_fee_amount="60000",
    )


def test_revenue_ledger_persists_customer_recovery_separately_from_platform_fee(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    revenue_id = ledger.create(_record(), billing_owner_id="warrantyguard")

    persisted = ledger.get(revenue_id)
    assert persisted["recovery_amount"] == Decimal("400000.00")
    assert persisted["platform_fee_amount"] == Decimal("60000.00")
    assert persisted["recovery_amount"] != persisted["platform_fee_amount"]

    report = ledger.report()
    assert report["customer_recovery_amount"] == Decimal("400000.00")
    assert report["platform_revenue_amount"] == Decimal("60000.00")


def test_engagement_identity_is_unique_per_factory(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    ledger.create(_record(), billing_owner_id="warrantyguard")
    with pytest.raises(BillingStateError):
        ledger.create(_record(), billing_owner_id="warrantyguard")


def test_state_history_is_durable_and_paid_requires_evidence(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    revenue_id = ledger.create(_record(), billing_owner_id="warrantyguard")

    for state in ("FEE_EARNED", "INVOICE_APPROVED", "INVOICED", "PAYMENT_PENDING"):
        ledger.transition(revenue_id, state)

    with pytest.raises(BillingStateError):
        ledger.transition(revenue_id, "PAID")

    paid = ledger.transition(
        revenue_id,
        "PAID",
        evidence_ref="stripe:invoice:synthetic-paid",
        provider_event_id="evt_paid_1",
    )
    assert paid["state"] == "PAID"
    reconciled = ledger.transition(
        revenue_id,
        "RECONCILED",
        evidence_ref="reconcile:invoice:synthetic-paid",
        provider_event_id="evt_paid_1",
    )
    assert reconciled["state"] == "RECONCILED"
    assert [item["new_state"] for item in ledger.transitions(revenue_id)] == [
        "FEE_EARNED",
        "INVOICE_APPROVED",
        "INVOICED",
        "PAYMENT_PENDING",
        "PAID",
        "RECONCILED",
    ]


def test_provider_refs_are_append_only_and_provider_owner_cannot_change(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    revenue_id = ledger.create(_record(), billing_owner_id="warrantyguard")

    ledger.attach_provider_ref(revenue_id, "customer", "cus_test", provider="stripe")
    ledger.attach_provider_ref(revenue_id, "invoice", "in_test", provider="stripe")
    ledger.attach_provider_ref(revenue_id, "invoice", "in_test", provider="stripe")

    with pytest.raises(BillingStateError):
        ledger.attach_provider_ref(revenue_id, "invoice", "in_other", provider="stripe")
    with pytest.raises(BillingStateError):
        ledger.attach_provider_ref(revenue_id, "payment", "pay_test", provider="other")


def test_provider_events_are_idempotent_but_conflicting_reuse_fails_closed(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    payload = '{"id":"evt_1","type":"invoice.paid"}'

    assert ledger.record_provider_event(
        provider="stripe",
        provider_event_id="evt_1",
        event_type="invoice.paid",
        object_ref="in_1",
        payload=payload,
    ) is True
    assert ledger.record_provider_event(
        provider="stripe",
        provider_event_id="evt_1",
        event_type="invoice.paid",
        object_ref="in_1",
        payload=payload,
    ) is False

    with pytest.raises(BillingStateError):
        ledger.record_provider_event(
            provider="stripe",
            provider_event_id="evt_1",
            event_type="invoice.voided",
            object_ref="in_1",
            payload='{"id":"evt_1","type":"invoice.voided"}',
        )
