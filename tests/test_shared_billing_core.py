from decimal import Decimal

import pytest

from factory_cloud.billing_core import (
    BillingConfigurationError,
    BillingStateError,
    advance_revenue_record,
    bank_destination_from_env,
    billing_plan,
    billing_route_for,
    create_revenue_record,
    load_billing_policy,
    payment_instructions,
    success_fee,
)
from factory_cloud.factory_switchboard import load_switchboard


def test_every_registered_factory_has_a_billing_route_and_current_portfolio_is_frozen():
    registry = load_switchboard()
    policy = load_billing_policy()
    plan = billing_plan(registry, policy)

    assert plan["registered_factories"] == len(registry["factories"]) == 42
    assert plan["billing_owners"] == 29
    assert plan["all_registered_factories_covered"] is True
    assert plan["real_provider_calls_enabled"] is False
    assert plan["bank_secret_embedded_in_repository"] is False
    assert plan["provider_ids_embedded_in_repository"] is False
    assert plan["provider_catalog_strategy"] == "metadata_factory_id_lookup"
    assert {route["factory_id"] for route in plan["routes"]} == {
        factory["id"] for factory in registry["factories"]
    }

    required_latest = {
        "guarantee-release",
        "royalty-recover",
        "debt-recover",
        "grid-recover",
        "govmargin",
        "contract-credit",
        "deal-recover",
        "earnedcash",
        "engineering-change-recoverability",
    }
    assert required_latest.issubset({factory["id"] for factory in registry["factories"]})


def test_obrasignal_owns_subscription_and_subfactories_inherit_it():
    registry = load_switchboard()
    policy = load_billing_policy()

    parent = billing_route_for("obrasignal", registry, policy)
    child = billing_route_for("obrasignal-data-runner", registry, policy)

    assert parent.mode == "subscription"
    assert parent.payment_rail == "revenuecat_store"
    assert parent.provider == "revenuecat"
    assert parent.collection_rails == ("app_store", "google_play")
    assert parent.product_id == "obrasignal_pro_monthly"
    assert parent.entitlement == "pro"
    assert child.mode == "inherit"
    assert child.billing_owner_id == "obrasignal"
    assert child.payment_rail == "revenuecat_store"
    assert child.provider == "revenuecat"


def test_k3_is_supporter_only_and_does_not_grant_paid_entitlement():
    registry = load_switchboard()
    policy = load_billing_policy()
    route = billing_route_for("k3-fatality", registry, policy)

    assert route.mode == "supporter_contribution"
    assert route.payment_rail == "supporter_checkout"
    assert route.provider == "stripe"
    assert route.collection_rails == ("stripe_supporter_checkout",)
    assert route.subscription_enabled is False
    assert route.grants_entitlement is False


def test_b2b_factories_share_stripe_invoice_and_direct_bank_rails():
    registry = load_switchboard()
    policy = load_billing_policy()

    warranty = billing_route_for("warrantyguard", registry, policy)
    aviation = billing_route_for("aviation-lease-entitlement-recovery", registry, policy)

    assert warranty.mode == aviation.mode == "b2b_invoice"
    assert warranty.payment_rail == aviation.payment_rail == "b2b_invoice"
    assert warranty.provider == aviation.provider == "stripe"
    assert warranty.collection_rails == aviation.collection_rails == (
        "stripe_hosted_invoice",
        "direct_bank_transfer",
    )
    assert warranty.currency == aviation.currency == "EUR"


def test_bank_destination_is_secret_backed_and_fail_closed():
    policy = load_billing_policy()
    with pytest.raises(BillingConfigurationError):
        bank_destination_from_env(policy, {})

    destination = bank_destination_from_env(
        policy,
        {
            "FACTORY_BILLING_IBAN": "GB82 WEST 1234 5698 7654 32",
            "FACTORY_BILLING_BIC": "DABAIE2D",
        },
    )
    assert destination.iban == "GB82WEST12345698765432"
    assert destination.masked_iban.startswith("GB82")
    assert destination.masked_iban.endswith("5432")
    assert destination.iban not in destination.masked_iban


def test_b2b_stripe_route_does_not_require_iban_but_explicit_direct_bank_does():
    registry = load_switchboard()
    policy = load_billing_policy()

    instructions = payment_instructions(
        "warrantyguard",
        registry=registry,
        policy=policy,
        environ={},
    )
    assert instructions["payment_rail"] == "b2b_invoice"
    assert instructions["provider"] == "stripe"
    assert instructions["provider_call_performed"] is False
    assert instructions["direct_bank_transfer"] == {"configured": False}
    assert "stripe_hosted_invoice" in instructions["collection_rails"]

    with pytest.raises(BillingConfigurationError):
        payment_instructions(
            "warrantyguard",
            registry=registry,
            policy=policy,
            environ={},
            include_full_bank_destination=True,
        )

    masked = payment_instructions(
        "warrantyguard",
        registry=registry,
        policy=policy,
        environ={"FACTORY_BILLING_IBAN": "GB82WEST12345698765432"},
    )
    assert masked["direct_bank_transfer"]["configured"] is True
    assert "iban" not in masked["direct_bank_transfer"]
    assert masked["direct_bank_transfer"]["masked_iban"].startswith("GB82")

    full = payment_instructions(
        "warrantyguard",
        registry=registry,
        policy=policy,
        environ={"FACTORY_BILLING_IBAN": "GB82WEST12345698765432"},
        include_full_bank_destination=True,
    )
    assert full["direct_bank_transfer"]["iban"] == "GB82WEST12345698765432"


def test_success_fee_keeps_customer_recovery_separate_from_platform_revenue():
    assert success_fee("400000", "15") == Decimal("60000.00")

    record = create_revenue_record(
        factory_id="warrantyguard",
        engagement_id="WG-1",
        customer_id="customer-1",
        recovery_amount="400000",
        platform_fee_amount="60000",
    )
    assert record.recovery_amount == Decimal("400000.00")
    assert record.platform_fee_amount == Decimal("60000.00")
    assert record.recovery_amount != record.platform_fee_amount


def test_paid_state_requires_durable_payment_evidence():
    record = create_revenue_record(
        factory_id="warrantyguard",
        engagement_id="WG-2",
        customer_id="customer-2",
        platform_fee_amount="1000",
    )
    record = advance_revenue_record(record, "FEE_EARNED")
    record = advance_revenue_record(record, "INVOICE_APPROVED")
    record = advance_revenue_record(record, "INVOICED")
    record = advance_revenue_record(record, "PAYMENT_PENDING")

    with pytest.raises(BillingStateError):
        advance_revenue_record(record, "PAID")

    paid = advance_revenue_record(record, "PAID", evidence_ref="bank:statement-line-123")
    assert paid.state == "PAID"
    reconciled = advance_revenue_record(paid, "RECONCILED", evidence_ref="reconcile:invoice-123")
    assert reconciled.state == "RECONCILED"


def test_supporter_and_subscription_paths_do_not_require_invoice_transition():
    record = create_revenue_record(
        factory_id="k3-fatality",
        engagement_id="support-1",
        customer_id="supporter-1",
        platform_fee_amount="5",
    )
    pending = advance_revenue_record(record, "PAYMENT_PENDING")
    paid = advance_revenue_record(pending, "PAID", evidence_ref="provider:event-1")
    assert paid.state == "PAID"
