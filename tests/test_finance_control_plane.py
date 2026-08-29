from factory_cloud.finance_control_plane import finance_status
from factory_cloud.revenue_ledger import RevenueLedger
from factory_cloud.billing_core import create_revenue_record


def test_finance_control_plane_covers_portfolio_without_exposing_secrets():
    secret = "sk_test_super_secret_value"
    webhook = "whsec_super_secret_value"
    iban = "GB82WEST12345698765432"
    status = finance_status(
        environ={
            "FACTORY_STRIPE_SECRET_KEY": secret,
            "FACTORY_STRIPE_WEBHOOK_SECRET": webhook,
            "FACTORY_STRIPE_LIVEMODE": "false",
            "FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED": "false",
            "FACTORY_BILLING_IBAN": iban,
        }
    )

    assert status["registered_factories"] == 42
    assert status["billing_owners"] == 29
    assert status["all_registered_factories_covered"] is True
    assert status["runtime"]["stripe_runtime_flags_ready"] is True
    assert status["runtime"]["stripe_mode"] == "TEST_REQUESTED"
    assert status["runtime"]["live_write_flags_ready"] is False
    assert status["runtime"]["live_customer_delivery_flags_ready"] is False
    assert status["runtime"]["production_gates_declared"]["all_declared_ready"] is False
    assert status["runtime"]["direct_bank"]["configured"] is True
    assert status["runtime"]["direct_bank"]["masked_iban"].startswith("GB82")
    assert status["runtime"]["secrets_exposed"] is False
    assert status["runtime"]["full_iban_exposed"] is False

    rendered = repr(status)
    assert secret not in rendered
    assert webhook not in rendered
    assert iban not in rendered


def test_live_mode_stays_blocked_until_all_three_production_gates_are_declared():
    base = {
        "FACTORY_STRIPE_SECRET_KEY": "sk_live_not_real",
        "FACTORY_STRIPE_WEBHOOK_SECRET": "whsec_not_real",
        "FACTORY_STRIPE_LIVEMODE": "true",
        "FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED": "true",
    }
    blocked = finance_status(environ=base)
    assert blocked["runtime"]["stripe_runtime_flags_ready"] is True
    assert blocked["runtime"]["live_write_flags_ready"] is False
    assert blocked["runtime"]["live_customer_delivery_flags_ready"] is False

    declared = finance_status(
        environ={
            **base,
            "FACTORY_PRODUCTION_LEGAL_ENTITY_VERIFIED": "true",
            "FACTORY_PRODUCTION_FISCAL_INVOICE_READY": "true",
            "FACTORY_PRODUCTION_PAYOUT_BANK_VERIFIED": "true",
        }
    )
    assert declared["runtime"]["production_gates_declared"]["all_declared_ready"] is True
    assert declared["runtime"]["live_write_flags_ready"] is True
    assert declared["runtime"]["live_customer_delivery_flags_ready"] is True
    assert declared["production_truth"] == {
        "provider_live_operation_verified": False,
        "bank_payout_verified": False,
        "fiscal_invoice_compliance_verified": False,
        "legal_entity_verified_by_control_plane": False,
        "reason": (
            "runtime declarations only unlock code paths; they are not independent evidence "
            "of provider operation, bank settlement, fiscal compliance or legal-entity status"
        ),
    }


def test_finance_status_can_include_ledger_totals_without_conflating_recovery(tmp_path):
    ledger = RevenueLedger(tmp_path / "finance.sqlite3")
    revenue_id = ledger.create(
        create_revenue_record(
            factory_id="warrantyguard",
            engagement_id="WG-REPORT",
            customer_id="customer-1",
            recovery_amount="100000",
            platform_fee_amount="10000",
        ),
        billing_owner_id="warrantyguard",
    )
    ledger.transition(revenue_id, "FEE_EARNED")

    status = finance_status(environ={}, ledger=ledger)
    assert status["ledger"]["customer_recovery_amount"] == "100000.00"
    assert status["ledger"]["platform_revenue_amount"] == "10000.00"
    assert status["ledger"]["by_factory"]["warrantyguard"]["recovery_amount"] == "100000.00"
    assert status["ledger"]["by_factory"]["warrantyguard"]["platform_fee_amount"] == "10000.00"
