from decimal import Decimal as D

import pytest

from cloud_switching.domain import MigrationCase, calculate


def case(**overrides):
    values = dict(
        case_id="transition-costs",
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
        provider_credit_approved=D("0"),
        provider_credit_received=D("0"),
        partner_incentive_approved=D("0"),
        partner_incentive_received=D("0"),
    )
    values.update(overrides)
    return MigrationCase(**values)


def test_transition_costs_are_included_in_gross_switching_cost():
    result = calculate(
        case(
            data_movement_cost=D("12000"),
            decommissioning_cost=D("8000"),
            backup_dr_transition_cost=D("7000"),
            security_transition_cost=D("6000"),
            support_transition_cost=D("5000"),
        )
    )
    assert result.gross_switching_cost == D("138000")
    assert result.year_one_economic_effect == D("-18000")
    assert result.economic_payback_months == D("13.80")


def test_legacy_egress_field_is_counted_for_compatibility():
    result = calculate(case(egress_data_movement_cost=D("12000")))
    assert result.gross_switching_cost == D("112000")


def test_data_movement_cost_cannot_be_double_counted_through_aliases():
    with pytest.raises(ValueError, match="both compatibility fields"):
        calculate(
            case(
                data_movement_cost=D("12000"),
                egress_data_movement_cost=D("12000"),
            )
        )


def test_transition_costs_can_destroy_an_apparently_positive_year_one_case():
    without_hidden_costs = calculate(case())
    with_hidden_costs = calculate(
        case(
            data_movement_cost=D("15000"),
            decommissioning_cost=D("10000"),
            backup_dr_transition_cost=D("10000"),
            security_transition_cost=D("10000"),
            support_transition_cost=D("5000"),
        )
    )
    assert without_hidden_costs.year_one_economic_effect == D("20000")
    assert with_hidden_costs.year_one_economic_effect == D("-30000")
