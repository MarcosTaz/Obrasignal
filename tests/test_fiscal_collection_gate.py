import json

import pytest

from factory_cloud.billing_core import BillingConfigurationError, BillingStateError
from factory_cloud.billing_service import SharedBillingService
from factory_cloud.revenue_ledger import RevenueLedger
from factory_cloud.stripe_billing_provider import StripeBillingProvider, StripeProviderConfig


class LiveInvoiceTransport:
    def __init__(self, *, retrieved_fiscal_ref="AT-FT-2026-000001"):
        self.calls = []
        self.retrieved_fiscal_ref = retrieved_fiscal_ref

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if url.endswith("/invoiceitems"):
            payload = {"id": "ii_live", "object": "invoiceitem", "livemode": True}
        elif url.endswith("/invoices"):
            payload = {"id": "in_live", "object": "invoice", "status": "draft", "livemode": True}
        elif url.endswith("/invoices/in_live/finalize"):
            payload = {
                "id": "in_live",
                "object": "invoice",
                "status": "open",
                "livemode": True,
            }
        elif method == "GET" and url.endswith("/invoices/in_live"):
            metadata = {}
            if self.retrieved_fiscal_ref:
                metadata["fiscal_document_ref"] = self.retrieved_fiscal_ref
            payload = {
                "id": "in_live",
                "object": "invoice",
                "status": "open",
                "livemode": True,
                "metadata": metadata,
            }
        elif url.endswith("/invoices/in_live/send"):
            payload = {
                "id": "in_live",
                "object": "invoice",
                "status": "open",
                "livemode": True,
            }
        else:
            raise AssertionError((method, url))
        return 200, json.dumps(payload).encode("utf-8")


def _live_provider(transport, *, delivery=True):
    return StripeBillingProvider(
        StripeProviderConfig(
            secret_key="sk_live_not_real",
            webhook_secret="whsec_not_real",
            livemode=True,
            customer_delivery_enabled=delivery,
            production_legal_entity_verified=True,
            production_fiscal_invoice_ready=True,
            production_payout_bank_verified=True,
        ),
        transport=transport,
    )


def test_live_stripe_collection_requires_concrete_fiscal_document_ref_before_any_write():
    transport = LiveInvoiceTransport()
    provider = _live_provider(transport)

    with pytest.raises(BillingConfigurationError):
        provider.create_b2b_invoice(
            customer_ref="cus_live",
            factory_id="warrantyguard",
            engagement_id="WG-LIVE-1",
            fee_amount="1000",
            description="Live fee",
        )
    assert transport.calls == []


def test_live_stripe_collection_carries_fiscal_reference_in_provider_metadata():
    transport = LiveInvoiceTransport()
    provider = _live_provider(transport)

    invoice = provider.create_b2b_invoice(
        customer_ref="cus_live",
        factory_id="warrantyguard",
        engagement_id="WG-LIVE-2",
        fee_amount="1000",
        description="Live fee",
        fiscal_document_ref="AT-FT-2026-000001",
    )
    assert invoice["id"] == "in_live"
    invoice_item_body = transport.calls[0][3].decode("utf-8")
    invoice_body = transport.calls[1][3].decode("utf-8")
    assert "fiscal_document_ref" in invoice_item_body
    assert "AT-FT-2026-000001" in invoice_item_body
    assert "fiscal_document_ref" in invoice_body
    assert "AT-FT-2026-000001" in invoice_body


def test_live_send_rechecks_authoritative_stripe_invoice_for_fiscal_reference():
    missing_transport = LiveInvoiceTransport(retrieved_fiscal_ref=None)
    missing = _live_provider(missing_transport)
    with pytest.raises(BillingConfigurationError):
        missing.send_invoice(
            "in_live", factory_id="warrantyguard", engagement_id="WG-LIVE-3"
        )
    assert [call[0] for call in missing_transport.calls] == ["GET"]

    transport = LiveInvoiceTransport(retrieved_fiscal_ref="AT-FT-2026-000003")
    provider = _live_provider(transport)
    result = provider.send_invoice(
        "in_live", factory_id="warrantyguard", engagement_id="WG-LIVE-3"
    )
    assert result["id"] == "in_live"
    assert [call[0] for call in transport.calls] == ["GET", "POST"]


def test_shared_service_requires_fiscal_reference_at_live_invoice_approval(tmp_path):
    transport = LiveInvoiceTransport()
    provider = _live_provider(transport)
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger, stripe_provider=provider)
    revenue_id = service.register_b2b_fee(
        factory_id="warrantyguard",
        engagement_id="WG-LIVE-4",
        customer_id="customer-live",
        platform_fee_amount="2500",
    )

    with pytest.raises(BillingConfigurationError):
        service.approve_invoice(revenue_id)
    assert ledger.get(revenue_id)["state"] == "FEE_EARNED"

    approved = service.approve_invoice(
        revenue_id, fiscal_document_ref="AT-FT-2026-000004"
    )
    assert approved["state"] == "INVOICE_APPROVED"
    assert approved["evidence_ref"] == "fiscal:AT-FT-2026-000004"

    invoice = service.create_stripe_invoice(
        revenue_id,
        provider_customer_ref="cus_live",
        description="Live fee collection",
    )
    assert invoice["id"] == "in_live"
    assert ledger.get(revenue_id)["state"] == "PAYMENT_PENDING"
    assert ledger.get(revenue_id)["evidence_ref"] == "fiscal:AT-FT-2026-000004"


def test_direct_bank_collection_also_requires_fiscal_document_reference(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    service = SharedBillingService(ledger)
    revenue_id = service.register_b2b_fee(
        factory_id="aviation-lease-entitlement-recovery",
        engagement_id="AV-FISCAL-1",
        customer_id="customer-1",
        platform_fee_amount="25000",
    )

    with pytest.raises(BillingStateError):
        service.open_direct_bank_collection(revenue_id, fiscal_document_ref="")
    assert ledger.get(revenue_id)["state"] == "FEE_EARNED"

    pending = service.open_direct_bank_collection(
        revenue_id, fiscal_document_ref="AT-FT-2026-000005"
    )
    assert pending["state"] == "PAYMENT_PENDING"
    assert pending["evidence_ref"] == "fiscal:AT-FT-2026-000005"
