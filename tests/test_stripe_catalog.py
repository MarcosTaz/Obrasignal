import json
from urllib.parse import parse_qs, urlparse

import pytest

from factory_cloud.billing_core import BillingConfigurationError
from factory_cloud.stripe_billing_provider import StripeBillingProvider, StripeProviderConfig
from factory_cloud.stripe_catalog import (
    b2b_billing_owners,
    ensure_b2b_product,
    sync_b2b_catalog,
)


class CatalogTransport:
    def __init__(self, *, existing=None, duplicates=None):
        self.existing = set(existing or set())
        self.duplicates = set(duplicates or set())
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if "/products/search" in url:
            query = parse_qs(urlparse(url).query).get("query", [""])[0]
            factory_id = query.split("'")[-2] if "'" in query else ""
            count = 2 if factory_id in self.duplicates else (1 if factory_id in self.existing else 0)
            data = [
                {
                    "id": f"prod_{factory_id}_{index}",
                    "object": "product",
                    "active": True,
                    "livemode": False,
                    "metadata": {
                        "factory_id": factory_id,
                        "billing_model": "b2b_invoice_dynamic",
                    },
                }
                for index in range(count)
            ]
            return 200, json.dumps({"object": "search_result", "data": data}).encode("utf-8")
        if url.endswith("/products") and method == "POST":
            return 200, json.dumps({"id": "prod_created", "object": "product", "livemode": False}).encode("utf-8")
        raise AssertionError((method, url))


def _provider(transport):
    return StripeBillingProvider(
        StripeProviderConfig(
            secret_key="sk_test_not_real",
            webhook_secret="whsec_not_real",
            livemode=False,
        ),
        transport=transport,
    )


def test_current_portfolio_has_26_distinct_b2b_catalog_owners():
    owners = b2b_billing_owners()
    ids = {item["factory_id"] for item in owners}
    assert len(owners) == len(ids) == 26
    assert "warrantyguard" in ids
    assert "royalty-recover" in ids
    assert "govmargin" in ids
    assert "k3-fatality" not in ids
    assert "obrasignal" not in ids
    assert "eu-switching-evidence-pack" not in ids
    assert "complianceledger" not in ids


def test_existing_product_is_reused_and_not_created_again():
    transport = CatalogTransport(existing={"warrantyguard"})
    result = ensure_b2b_product(
        _provider(transport),
        factory_id="warrantyguard",
        name="WarrantyGuard",
        allow_create=True,
    )
    assert result == {
        "factory_id": "warrantyguard",
        "status": "EXISTS",
        "provider_ref_present": True,
    }
    assert len(transport.calls) == 1
    assert "/products/search" in transport.calls[0][1]


def test_missing_product_is_read_only_by_default():
    transport = CatalogTransport()
    result = ensure_b2b_product(
        _provider(transport),
        factory_id="warrantyguard",
        name="WarrantyGuard",
    )
    assert result["status"] == "MISSING"
    assert result["provider_ref_present"] is False
    assert len(transport.calls) == 1


def test_missing_product_can_be_created_only_with_explicit_gate():
    transport = CatalogTransport()
    result = ensure_b2b_product(
        _provider(transport),
        factory_id="warrantyguard",
        name="WarrantyGuard",
        allow_create=True,
    )
    assert result["status"] == "CREATED"
    assert len(transport.calls) == 2
    method, url, headers, body = transport.calls[-1]
    assert method == "POST"
    assert url.endswith("/products")
    assert headers["Idempotency-Key"].startswith("factory-finance-")
    decoded = body.decode("utf-8")
    assert "factory_id%5D=warrantyguard" in decoded
    assert "billing_model%5D=b2b_invoice_dynamic" in decoded


def test_duplicate_active_products_fail_closed():
    transport = CatalogTransport(duplicates={"warrantyguard"})
    with pytest.raises(BillingConfigurationError):
        ensure_b2b_product(
            _provider(transport),
            factory_id="warrantyguard",
            name="WarrantyGuard",
            allow_create=True,
        )


def test_catalog_sync_never_returns_provider_ids():
    owners = b2b_billing_owners()
    transport = CatalogTransport(existing={item["factory_id"] for item in owners})
    result = sync_b2b_catalog(_provider(transport), allow_create=False)
    assert result["expected_b2b_billing_owners"] == 26
    assert result["existing"] == 26
    assert result["created"] == 0
    assert result["missing"] == 0
    assert result["provider_ids_returned"] is False
    assert all("id" not in item for item in result["results"])
