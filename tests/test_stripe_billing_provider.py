import hashlib
import hmac
import json

import pytest

from factory_cloud.billing_core import BillingConfigurationError, BillingStateError
from factory_cloud.stripe_billing_provider import (
    BillingProviderError,
    StripeBillingProvider,
    StripeProviderConfig,
    eur_minor_units,
    stable_idempotency_key,
)


class FakeStripe:
    def __init__(self, *, livemode=False):
        self.calls = []
        self.livemode = livemode

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if url.endswith("/invoiceitems"):
            payload = {"id": "ii_test", "object": "invoiceitem", "livemode": self.livemode}
        elif url.endswith("/invoices"):
            payload = {"id": "in_test", "object": "invoice", "status": "draft", "livemode": self.livemode}
        elif url.endswith("/invoices/in_test/finalize"):
            payload = {"id": "in_test", "object": "invoice", "status": "open", "livemode": self.livemode}
        elif url.endswith("/invoices/in_test/send"):
            payload = {"id": "in_test", "object": "invoice", "status": "open", "livemode": self.livemode}
        else:
            payload = {"id": "cus_test", "object": "customer", "livemode": self.livemode}
        return 200, json.dumps(payload).encode("utf-8")


def _config(**kwargs):
    values = {
        "secret_key": "sk_test_not_real",
        "webhook_secret": "whsec_not_real",
        "livemode": False,
        "customer_delivery_enabled": False,
    }
    values.update(kwargs)
    return StripeProviderConfig(**values)


def test_provider_secrets_fail_closed_and_delivery_defaults_off():
    with pytest.raises(BillingConfigurationError):
        StripeProviderConfig.from_env({})

    config = StripeProviderConfig.from_env(
        {
            "FACTORY_STRIPE_SECRET_KEY": "sk_test_not_real",
            "FACTORY_STRIPE_WEBHOOK_SECRET": "whsec_not_real",
        }
    )
    assert config.livemode is False
    assert config.customer_delivery_enabled is False


def test_eur_minor_units_are_exact_and_negative_amounts_fail():
    assert eur_minor_units("60000") == 6000000
    assert eur_minor_units("10.01") == 1001
    with pytest.raises(BillingStateError):
        eur_minor_units("-0.01")


def test_b2b_invoice_creation_is_idempotent_and_does_not_send_customer_email():
    fake = FakeStripe()
    provider = StripeBillingProvider(_config(), transport=fake)

    invoice = provider.create_b2b_invoice(
        customer_ref="cus_test",
        factory_id="warrantyguard",
        engagement_id="WG-SYNTH-001",
        fee_amount="60000",
        description="Synthetic fee",
    )
    assert invoice["id"] == "in_test"
    assert invoice["status"] == "open"
    assert [call[1].rsplit("/v1", 1)[-1] for call in fake.calls] == [
        "/invoiceitems",
        "/invoices",
        "/invoices/in_test/finalize",
    ]
    assert all(not call[1].endswith("/send") for call in fake.calls)

    keys = [call[2].get("Idempotency-Key") for call in fake.calls]
    assert keys == [
        stable_idempotency_key("warrantyguard", "WG-SYNTH-001", "invoice-item"),
        stable_idempotency_key("warrantyguard", "WG-SYNTH-001", "invoice"),
        stable_idempotency_key("warrantyguard", "WG-SYNTH-001", "finalize"),
    ]
    invoice_body = fake.calls[1][3].decode("utf-8")
    assert "auto_advance=false" in invoice_body
    assert "pending_invoice_items_behavior=include" in invoice_body


def test_customer_delivery_requires_explicit_runtime_gate():
    fake = FakeStripe()
    provider = StripeBillingProvider(_config(), transport=fake)
    with pytest.raises(BillingConfigurationError):
        provider.send_invoice("in_test", factory_id="warrantyguard", engagement_id="WG-1")
    assert fake.calls == []

    allowed = StripeBillingProvider(_config(customer_delivery_enabled=True), transport=fake)
    result = allowed.send_invoice("in_test", factory_id="warrantyguard", engagement_id="WG-1")
    assert result["id"] == "in_test"
    assert fake.calls[-1][1].endswith("/invoices/in_test/send")


def test_provider_livemode_mismatch_fails_closed():
    fake = FakeStripe(livemode=True)
    provider = StripeBillingProvider(_config(livemode=False), transport=fake)
    with pytest.raises(BillingProviderError):
        provider.create_customer(
            customer_key="customer-1",
            name="Synthetic",
            email="billing-test@example.com",
            factory_id="warrantyguard",
        )


def test_webhook_signature_and_paid_evidence_are_verified():
    timestamp = 1_800_000_000
    event = {
        "id": "evt_paid_1",
        "type": "invoice.paid",
        "livemode": False,
        "data": {
            "object": {
                "id": "in_paid_1",
                "object": "invoice",
                "metadata": {
                    "factory_id": "warrantyguard",
                    "engagement_id": "WG-1",
                },
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    secret = "whsec_not_real"
    signature = hmac.new(
        secret.encode("utf-8"), str(timestamp).encode("ascii") + b"." + payload, hashlib.sha256
    ).hexdigest()
    provider = StripeBillingProvider(_config(webhook_secret=secret), transport=FakeStripe())

    verified = provider.verify_webhook(payload, f"t={timestamp},v1={signature}", now=timestamp)
    evidence = provider.paid_event_evidence(verified)
    assert evidence == {
        "provider": "stripe",
        "provider_event_id": "evt_paid_1",
        "invoice_ref": "in_paid_1",
        "factory_id": "warrantyguard",
        "engagement_id": "WG-1",
        "evidence_ref": "stripe:event:evt_paid_1:invoice:in_paid_1",
    }

    with pytest.raises(BillingProviderError):
        provider.verify_webhook(payload, f"t={timestamp},v1={signature}", now=timestamp + 301)


def test_non_paid_event_cannot_prove_payment():
    provider = StripeBillingProvider(_config(), transport=FakeStripe())
    with pytest.raises(BillingStateError):
        provider.paid_event_evidence({"id": "evt_1", "type": "invoice.finalized", "livemode": False})
