import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from factory_cloud.billing_core import BillingConfigurationError, BillingStateError
from factory_cloud.billing_service import SharedBillingService
from factory_cloud.revenue_ledger import RevenueLedger
from factory_cloud.stripe_billing_provider import StripeBillingProvider, StripeProviderConfig


class FakeStripeTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if url.endswith("/invoiceitems"):
            payload = {"id": "ii_test", "object": "invoiceitem", "livemode": False}
        elif url.endswith("/invoices"):
            payload = {"id": "in_test", "object": "invoice", "status": "draft", "livemode": False}
        elif url.endswith("/invoices/in_test/finalize"):
            payload = {"id": "in_test", "object": "invoice", "status": "open", "livemode": False}
        elif url.endswith("/invoices/in_test/send"):
            payload = {"id": "in_test", "object": "invoice", "status": "open", "livemode": False}
        else:
            payload = {"id": "unknown", "livemode": False}
        return 200, json.dumps(payload).encode("utf-8")


def _provider(*, delivery=False):
    config = StripeProviderConfig(
        secret_key="sk_test_not_real",
        webhook_secret="whsec_test_not_real",
        livemode=False,
        customer_delivery_enabled=delivery,
    )
    return StripeBillingProvider(config, transport=FakeStripeTransport())


def _signature(payload, *, timestamp=1_800_000_000, secret="whsec_test_not_real"):
    digest = hmac.new(
        secret.encode("utf-8"),
        str(timestamp).encode("ascii") + b"." + payload,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_b2b_success_fee_to_stripe_invoice_to_paid_webhook(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    provider = _provider()
    service = SharedBillingService(ledger, stripe_provider=provider)

    revenue_id = service.register_b2b_fee(
        factory_id="warrantyguard",
        engagement_id="WG-1",
        customer_id="customer-1",
        recovery_amount="400000",
        success_fee_percentage="15",
    )
    earned = ledger.get(revenue_id)
    assert earned["state"] == "FEE_EARNED"
    assert earned["recovery_amount"] == Decimal("400000.00")
    assert earned["platform_fee_amount"] == Decimal("60000.00")

    service.approve_invoice(revenue_id)
    invoice = service.create_stripe_invoice(
        revenue_id,
        provider_customer_ref="cus_test",
        description="Synthetic WarrantyGuard fee",
    )
    assert invoice["id"] == "in_test"
    pending = ledger.get(revenue_id)
    assert pending["state"] == "PAYMENT_PENDING"
    assert pending["provider"] == "stripe"
    assert pending["provider_customer_ref"] == "cus_test"
    assert pending["provider_invoice_ref"] == "in_test"

    event = {
        "id": "evt_paid_1",
        "type": "invoice.paid",
        "livemode": False,
        "data": {
            "object": {
                "id": "in_test",
                "object": "invoice",
                "metadata": {"factory_id": "warrantyguard", "engagement_id": "WG-1"},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    result = service.ingest_stripe_webhook(
        payload, _signature(payload), now=1_800_000_000
    )
    assert result["state"] == "PAID"
    assert result["state_changed"] is True
    assert ledger.get(revenue_id)["evidence_ref"] == "stripe:event:evt_paid_1:invoice:in_test"

    duplicate = service.ingest_stripe_webhook(
        payload, _signature(payload), now=1_800_000_000
    )
    assert duplicate["duplicate"] is True
    assert duplicate["state_changed"] is False


def test_invoice_delivery_is_still_explicitly_blocked(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger, stripe_provider=_provider(delivery=False))
    revenue_id = service.register_b2b_fee(
        factory_id="capacity-commitment",
        engagement_id="CC-1",
        customer_id="customer-1",
        platform_fee_amount="1500",
    )
    service.approve_invoice(revenue_id)
    service.create_stripe_invoice(
        revenue_id,
        provider_customer_ref="cus_test",
        description="Synthetic assisted pilot",
    )
    with pytest.raises(BillingConfigurationError):
        service.send_stripe_invoice(revenue_id)


def test_invoice_paid_with_wrong_provider_invoice_fails_closed(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger, stripe_provider=_provider())
    revenue_id = service.register_b2b_fee(
        factory_id="warrantyguard",
        engagement_id="WG-2",
        customer_id="customer-1",
        platform_fee_amount="1000",
    )
    service.approve_invoice(revenue_id)
    service.create_stripe_invoice(
        revenue_id,
        provider_customer_ref="cus_test",
        description="Synthetic fee",
    )
    event = {
        "id": "evt_wrong",
        "type": "invoice.paid",
        "livemode": False,
        "data": {
            "object": {
                "id": "in_different",
                "object": "invoice",
                "metadata": {"factory_id": "warrantyguard", "engagement_id": "WG-2"},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    with pytest.raises(BillingStateError):
        service.ingest_stripe_webhook(payload, _signature(payload), now=1_800_000_000)
    assert ledger.get(revenue_id)["state"] == "PAYMENT_PENDING"


def test_k3_paid_checkout_records_support_without_entitlement(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger, stripe_provider=_provider())
    event = {
        "id": "evt_k3_1",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_k3_1",
                "object": "checkout.session",
                "payment_status": "paid",
                "currency": "eur",
                "amount_total": 500,
                "payment_intent": "pi_k3_1",
                "customer": None,
                "metadata": {
                    "factory_id": "k3-fatality",
                    "billing_model": "voluntary_support",
                    "paid_entitlement": "none",
                },
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    result = service.ingest_stripe_webhook(payload, _signature(payload), now=1_800_000_000)
    assert result["state"] == "PAID"
    assert result["grants_entitlement"] is False
    record = ledger.find("k3-fatality", "cs_k3_1")
    assert record["platform_fee_amount"] == Decimal("5.00")
    assert record["recovery_amount"] is None
    assert record["provider_payment_ref"] == "pi_k3_1"

    duplicate = service.ingest_stripe_webhook(payload, _signature(payload), now=1_800_000_000)
    assert duplicate["duplicate"] is True
    assert duplicate["state_changed"] is False


def test_k3_completed_but_unpaid_checkout_cannot_create_revenue(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger, stripe_provider=_provider())
    event = {
        "id": "evt_k3_unpaid",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_k3_unpaid",
                "object": "checkout.session",
                "payment_status": "unpaid",
                "currency": "eur",
                "amount_total": 500,
                "metadata": {"factory_id": "k3-fatality"},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    with pytest.raises(BillingStateError):
        service.ingest_stripe_webhook(payload, _signature(payload), now=1_800_000_000)
    with pytest.raises(KeyError):
        ledger.find("k3-fatality", "cs_k3_unpaid")


def test_direct_bank_payment_and_reconciliation_require_evidence(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger)
    revenue_id = service.register_b2b_fee(
        factory_id="aviation-lease-entitlement-recovery",
        engagement_id="AV-1",
        customer_id="customer-1",
        platform_fee_amount="25000",
    )
    service.approve_invoice(revenue_id)
    ledger.transition(revenue_id, "INVOICED", evidence_ref="invoice:external:AV-1")
    ledger.transition(revenue_id, "PAYMENT_PENDING")

    with pytest.raises(BillingStateError):
        service.record_direct_bank_paid(revenue_id, bank_evidence_ref="")
    paid = service.record_direct_bank_paid(
        revenue_id, bank_evidence_ref="bank:statement:synthetic-line-1"
    )
    assert paid["state"] == "PAID"
    reconciled = service.reconcile(
        revenue_id, evidence_ref="reconcile:synthetic-bank-to-invoice-AV-1"
    )
    assert reconciled["state"] == "RECONCILED"
