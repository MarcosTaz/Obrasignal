import json

import pytest

from factory_cloud.billing_core import BillingConfigurationError
from factory_cloud.stripe_billing_provider import StripeBillingProvider, StripeProviderConfig
from factory_cloud.stripe_catalog import ensure_b2b_product


class LiveTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if "/products/search" in url:
            return 200, json.dumps({"object": "search_result", "data": []}).encode("utf-8")
        if url.endswith("/products"):
            return 200, json.dumps({"id": "prod_live", "object": "product", "livemode": True}).encode("utf-8")
        if url.endswith("/customers"):
            return 200, json.dumps({"id": "cus_live", "object": "customer", "livemode": True}).encode("utf-8")
        raise AssertionError((method, url))


def _live_config(**kwargs):
    values = {
        "secret_key": "sk_live_not_real",
        "webhook_secret": "whsec_not_real",
        "livemode": True,
        "customer_delivery_enabled": True,
        "production_legal_entity_verified": False,
        "production_fiscal_invoice_ready": False,
        "production_payout_bank_verified": False,
    }
    values.update(kwargs)
    return StripeProviderConfig(**values)


def test_live_customer_write_fails_before_transport_when_production_gates_are_missing():
    transport = LiveTransport()
    provider = StripeBillingProvider(_live_config(), transport=transport)
    with pytest.raises(BillingConfigurationError):
        provider.create_customer(
            customer_key="live-1",
            name="Live customer",
            email="billing@example.com",
            factory_id="warrantyguard",
        )
    assert transport.calls == []


def test_live_catalog_creation_fails_after_read_but_before_write_when_gates_are_missing():
    transport = LiveTransport()
    provider = StripeBillingProvider(_live_config(), transport=transport)
    with pytest.raises(BillingConfigurationError):
        ensure_b2b_product(
            provider,
            factory_id="warrantyguard",
            name="WarrantyGuard",
            allow_create=True,
        )
    assert len(transport.calls) == 1
    assert "/products/search" in transport.calls[0][1]
    assert all(not (method == "POST" and url.endswith("/products")) for method, url, _, _ in transport.calls)


def test_live_write_is_reachable_only_after_all_production_gates_are_declared():
    transport = LiveTransport()
    provider = StripeBillingProvider(
        _live_config(
            production_legal_entity_verified=True,
            production_fiscal_invoice_ready=True,
            production_payout_bank_verified=True,
        ),
        transport=transport,
    )
    assert provider.config.production_activation_ready is True
    customer = provider.create_customer(
        customer_key="live-2",
        name="Live customer",
        email="billing@example.com",
        factory_id="warrantyguard",
    )
    assert customer["id"] == "cus_live"
    assert len(transport.calls) == 1


def test_from_env_requires_all_three_declarations_for_live_activation():
    config = StripeProviderConfig.from_env(
        {
            "FACTORY_STRIPE_SECRET_KEY": "sk_live_not_real",
            "FACTORY_STRIPE_WEBHOOK_SECRET": "whsec_not_real",
            "FACTORY_STRIPE_LIVEMODE": "true",
            "FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED": "true",
            "FACTORY_PRODUCTION_LEGAL_ENTITY_VERIFIED": "true",
            "FACTORY_PRODUCTION_FISCAL_INVOICE_READY": "true",
            "FACTORY_PRODUCTION_PAYOUT_BANK_VERIFIED": "false",
        }
    )
    assert config.livemode is True
    assert config.customer_delivery_enabled is True
    assert config.production_activation_ready is False
