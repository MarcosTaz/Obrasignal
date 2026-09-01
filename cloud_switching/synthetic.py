from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict

from .domain import MigrationCase

D = Decimal


@dataclass(frozen=True)
class SyntheticCompany:
    name: str
    scenario: str
    case: MigrationCase
    oracle_should_migrate: bool
    oracle_reason: str


def _case(case_id: str, **overrides) -> MigrationCase:
    values = dict(
        case_id=case_id,
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


def synthetic_companies() -> Dict[str, SyntheticCompany]:
    return {
        "alpha_manufacturing_eu": SyntheticCompany(
            name="Alpha Manufacturing EU",
            scenario="large_savings",
            case=_case("alpha"),
            oracle_should_migrate=True,
            oracle_reason="status-quo avoidance exceeds unsubsidized switching cost within year one",
        ),
        "nova_services": SyntheticCompany(
            name="Nova Services",
            scenario="small_savings",
            case=_case(
                "nova",
                status_quo_annual_cost=D("220000"),
                target_annual_cost=D("210000"),
                migration_engineering_cost=D("15000"),
                partner_services_cost=D("10000"),
                internal_labour_cost=D("5000"),
                training_cost=D("2000"),
                parallel_run_cost=D("5000"),
                refactoring_cost=D("5000"),
                risk_contingency_cost=D("3000"),
                provider_credit_approved=D("0"),
                provider_credit_received=D("0"),
                partner_incentive_approved=D("0"),
                partner_incentive_received=D("0"),
            ),
            oracle_should_migrate=False,
            oracle_reason="positive annual saving does not recover switching cost quickly enough for this synthetic gate",
        ),
        "titan_enterprise": SyntheticCompany(
            name="Titan Enterprise",
            scenario="negative_value",
            case=_case(
                "titan",
                current_annual_cost=D("900000"),
                status_quo_annual_cost=D("1000000"),
                target_annual_cost=D("1100000"),
                migration_engineering_cost=D("180000"),
                partner_services_cost=D("160000"),
                internal_labour_cost=D("90000"),
                training_cost=D("30000"),
                parallel_run_cost=D("120000"),
                refactoring_cost=D("220000"),
                risk_contingency_cost=D("100000"),
                provider_credit_approved=D("150000"),
                provider_credit_received=D("100000"),
                partner_incentive_approved=D("50000"),
                partner_incentive_received=D("25000"),
            ),
            oracle_should_migrate=False,
            oracle_reason="target recurring cost exceeds status quo before switching cost",
        ),
        "hybrid_europe": SyntheticCompany(
            name="Hybrid Europe",
            scenario="economically_neutral",
            case=_case(
                "hybrid",
                status_quo_annual_cost=D("250000"),
                target_annual_cost=D("250000"),
                provider_credit_approved=D("40000"),
                provider_credit_received=D("40000"),
            ),
            oracle_should_migrate=False,
            oracle_reason="no recurring status-quo avoidance exists",
        ),
    }
