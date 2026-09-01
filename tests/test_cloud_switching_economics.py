from decimal import Decimal

import pytest

from cloud_switching.domain import MigrationCase, calculate
from cloud_switching.outcome import Evidence, EvidenceStrength, ForecastActual, MigrationOutcomeRecord

D = Decimal


def base_case(**overrides):
    values = dict(
        case_id="alpha",
        current_annual_cost=D("240000"),
        status_quo_annual_cost=D("300000"),
        target_annual_cost=D("180000"),
        migration_engineering_cost=D("30000"),
        partner_services_cost=D("20000"),
        internal_labour_cost=D("10000"),
        training_cost=D("5000"),
        parallel_run_cost=D("15000"),
        refactoring_cost=D("10000"),
        risk_contingency_cost=D("10000"),
        provider_credit_approved=D("30000"),
        provider_credit_received=D("25000"),
        partner_incentive_approved=D("10000"),
        partner_incentive_received=D("5000"),
    )
    values.update(overrides)
    return MigrationCase(**values)


def test_separates_gross_economics_from_provider_subsidy():
    result = calculate(base_case())
    assert result.gross_switching_cost == D("100000")
    assert result.received_capital == D("30000")
    assert result.customer_cash_switching_cost == D("70000")
    assert result.annual_status_quo_avoidance == D("120000")
    assert result.year_one_economic_effect == D("20000")
    assert result.year_one_customer_cash_effect == D("50000")
    assert result.economic_payback_months == D("10.00")
    assert result.customer_cash_payback_months == D("7.00")


def test_no_false_payback_when_target_is_more_expensive_than_status_quo():
    result = calculate(base_case(target_annual_cost=D("330000")))
    assert result.annual_status_quo_avoidance == D("-30000")
    assert result.economic_payback_months is None
    assert result.customer_cash_payback_months is None


def test_received_credit_cannot_exceed_approved_credit():
    with pytest.raises(ValueError):
        calculate(base_case(provider_credit_received=D("40000")))


def test_oversubsidy_never_produces_negative_payback_duration():
    result = calculate(
        base_case(
            provider_credit_approved=D("90000"),
            provider_credit_received=D("90000"),
            partner_incentive_approved=D("20000"),
            partner_incentive_received=D("20000"),
        )
    )
    assert result.customer_cash_switching_cost == D("-10000")
    assert result.customer_cash_payback_months == D("0.00")


def test_partner_self_attestation_is_excluded_from_verified_benchmark():
    partner = Evidence("partner-case", EvidenceStrength.PARTNER, False, "v0.1")
    field = ForecastActual(D("100"), D("90"), partner)
    record = MigrationOutcomeRecord("x", "vmware", "aws", "vm", "rehost", field, field, field, field, field)
    assert not record.verified_for_benchmark()


def test_non_independent_customer_attestation_is_excluded_from_verified_benchmark():
    customer = Evidence("customer-sheet", EvidenceStrength.CUSTOMER, False, "v0.1")
    field = ForecastActual(D("100"), D("90"), customer)
    record = MigrationOutcomeRecord("x", "vmware", "aws", "vm", "rehost", field, field, field, field, field)
    assert not record.verified_for_benchmark()


def test_machine_evidence_can_enter_verified_benchmark():
    machine = Evidence("billing-export", EvidenceStrength.MACHINE, True, "v0.1")
    field = ForecastActual(D("100"), D("90"), machine)
    record = MigrationOutcomeRecord("x", "vmware", "azure", "vm", "rehost", field, field, field, field, field)
    assert record.verified_for_benchmark()
    assert field.variance == D("-10")
    assert field.variance_pct == D("-10.00")
