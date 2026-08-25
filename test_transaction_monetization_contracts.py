from dataclasses import fields
from decimal import Decimal

import pytest

from transaction_monetization_contracts import (
    Commission,
    FinancingRoute,
    InsuranceRoute,
    MonetizationState,
    RegulatoryState,
    SupplierEconomicFit,
    evaluate_monetization_gate,
)


def _passing_gate(**updates):
    checks = dict(
        customer_experience_preserved=True,
        reduces_cost_or_friction=True,
        conflict_controlled=True,
        regulatory_clearance=True,
        trust_preserved=True,
        margin_justifies_complexity=True,
        measurable_and_auditable=True,
    )
    checks.update(updates)
    return evaluate_monetization_gate(**checks)


def test_monetization_gate_requires_every_control_to_pass():
    assert _passing_gate().state is MonetizationState.ELIGIBLE
    blocked = _passing_gate(trust_preserved=False)
    assert blocked.state is MonetizationState.BLOCKED
    assert blocked.failed_checks == ("trust_preserved",)


def test_monetization_gate_fails_closed_on_missing_evidence():
    with pytest.raises(ValueError, match="missing monetization gate checks"):
        evaluate_monetization_gate(customer_experience_preserved=True)


def test_finance_and_insurance_routes_require_authorized_or_cleared_partner_state():
    finance = FinancingRoute("f1", "tx1", "p1", "PT", RegulatoryState.UNKNOWN)
    insurance = InsuranceRoute("i1", "tx1", "p2", "PT", RegulatoryState.BLOCKED)
    assert finance.partner_route_eligible is False
    assert insurance.partner_route_eligible is False
    assert FinancingRoute("f2", "tx1", "p1", "PT", RegulatoryState.AUTHORIZED_PARTNER).partner_route_eligible
    assert InsuranceRoute("i2", "tx1", "p2", "PT", RegulatoryState.CLEARED).partner_route_eligible


def test_remuneration_cannot_be_encoded_in_supplier_ranking_contract():
    ranking_fields = {field.name for field in fields(SupplierEconomicFit)}
    prohibited = {"commission", "commission_rate", "referral", "referral_fee", "partner_payment", "paid_rank", "sponsored"}
    assert ranking_fields.isdisjoint(prohibited)
    assert {field.name for field in fields(Commission)} & ranking_fields == set()


def test_supplier_economic_fit_contains_only_customer_economic_inputs():
    fit = SupplierEconomicFit(
        supplier_id="s1",
        landed_cost=Decimal("100.00"),
        quality_score=Decimal("0.90"),
        compliance_passed=True,
        lead_time_days=5,
        reliability_score=Decimal("0.95"),
        payment_terms_score=Decimal("0.80"),
        risk_score=Decimal("0.10"),
        contractor_economic_fit=Decimal("0.92"),
    )
    assert fit.landed_cost == Decimal("100.00")
    assert not hasattr(fit, "commission")
