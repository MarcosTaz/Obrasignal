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


def test_every_registered_factory_has_a_billing_route():
    registry = load_switchboard()
    policy = load_billing_policy()
    plan = billing_plan(registry, policy)

    assert plan["registered_factories"] == len(registry["factories"])
    assert plan["all_registered_factories_covered"] is True
    assert plan["real_provider_calls_enabled"] is False
    assert plan["bank_secret_embedded_in_repository"] is False
    assert {route["factory_id"] for route in plan["routes"]} == {
        factory["id"] for factory in registry["factories"]
    }


def test_obrasignal_owns_subscription_and_subfactories_inherit_it():
    registry = load_switchboard()
    policy = load_billing_policy()

    parent = billing_route_for("obrasignal", registry, policy)
    child = billing_route_for("obrasignal-data-runner", registry, policy)

    assert parent.mode == "subscription"
    assert parent.payment_rail == "revenuecat_store"
    assert parent.product_id == "obrasignal_pro_monthly"
    assert parent.entitlement == "pro"
    assert child.mode == "inherit"
    assert child.billing_owner_id == "obrasignal"
    assert child.payment_rail == "revenuecat_store"


def test_k3_is_supporter_only_and_does_not_grant_paid_entitlement():
    registry = load_switchboard()
    policy = load_billing_policy()
    route = billing_route_for("k3-fatality", registry, policy)

    assert route.mode == "supporter_contribution"
    assert route.payment_rail == "supporter_checkout"
    assert route.subscription_enabled is False
    assert route.grants_entitlement is False


def test_b2b_factories_share_bank_transfer_rail():
    registry = load_switchboard()
    policy = load_billing_policy()

    warranty = billing_route_for("warrantyguard", registry, policy)
    aviation = billing_route_for("aviation-lease-entitlement-recovery", registry, policy)

    assert warranty.mode == aviation.mode == "b2b_invoice"
    assert warranty.payment_rail == aviation.payment_rail == "bank_transfer"
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


def test_b2b_payment_instructions_require_runtime_bank_configuration():
    registry = load_switchboard()
    policy = load_billing_policy()

    with pytest.raises(BillingConfigurationError):
        payment_instructions(
            "warrantyguard",
            registry=registry,
            policy=policy,
            environ={},
        )

    instructions = payment_instructions(
        "warrantyguard",
        registry=registry,
        policy=policy,
        environ={"FACTORY_BILLING_IBAN": "GB82WEST12345698765432"},
    )
    assert instructions["payment_rail"] == "bank_transfer"
    assert instructions["provider_call_performed"] is False
    assert instructions["bank_destination"]["iban"] == "GB82WEST12345698765432"


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
