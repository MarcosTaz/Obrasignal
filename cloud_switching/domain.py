from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

Money = Decimal


@dataclass(frozen=True)
class MigrationCase:
    case_id: str
    current_annual_cost: Money
    status_quo_annual_cost: Money
    target_annual_cost: Money
    migration_engineering_cost: Money
    partner_services_cost: Money
    internal_labour_cost: Money
    training_cost: Money
    parallel_run_cost: Money
    refactoring_cost: Money
    risk_contingency_cost: Money
    # Canonical external input is data_movement_cost; egress_data_movement_cost
    # remains an explicit compatibility field for earlier internal callers.
    data_movement_cost: Money = Decimal("0")
    egress_data_movement_cost: Money = Decimal("0")
    decommissioning_cost: Money = Decimal("0")
    backup_dr_transition_cost: Money = Decimal("0")
    security_transition_cost: Money = Decimal("0")
    support_transition_cost: Money = Decimal("0")
    provider_credit_approved: Money = Decimal("0")
    provider_credit_received: Money = Decimal("0")
    partner_incentive_approved: Money = Decimal("0")
    partner_incentive_received: Money = Decimal("0")
    observation_months: int = 12
    actual_post_annual_cost: Optional[Money] = None

    def validate(self) -> None:
        money_fields = (
            self.current_annual_cost,
            self.status_quo_annual_cost,
            self.target_annual_cost,
            self.migration_engineering_cost,
            self.partner_services_cost,
            self.internal_labour_cost,
            self.training_cost,
            self.parallel_run_cost,
            self.refactoring_cost,
            self.risk_contingency_cost,
            self.data_movement_cost,
            self.egress_data_movement_cost,
            self.decommissioning_cost,
            self.backup_dr_transition_cost,
            self.security_transition_cost,
            self.support_transition_cost,
            self.provider_credit_approved,
            self.provider_credit_received,
            self.partner_incentive_approved,
            self.partner_incentive_received,
        )
        if any(value < 0 for value in money_fields):
            raise ValueError("money values cannot be negative")
        if self.data_movement_cost and self.egress_data_movement_cost:
            raise ValueError("data movement cost cannot be supplied in both compatibility fields")
        if self.observation_months <= 0:
            raise ValueError("observation_months must be positive")
        if self.provider_credit_received > self.provider_credit_approved:
            raise ValueError("received provider credit cannot exceed approved credit")
        if self.partner_incentive_received > self.partner_incentive_approved:
            raise ValueError("received partner incentive cannot exceed approved incentive")

    @property
    def effective_data_movement_cost(self) -> Money:
        return self.data_movement_cost or self.egress_data_movement_cost


@dataclass(frozen=True)
class EconomicsResult:
    gross_switching_cost: Money
    received_capital: Money
    customer_cash_switching_cost: Money
    annual_status_quo_avoidance: Money
    annual_operating_saving: Money
    year_one_economic_effect: Money
    year_one_customer_cash_effect: Money
    economic_payback_months: Optional[Decimal]
    customer_cash_payback_months: Optional[Decimal]


def _payback_months(cost: Money, annual_saving: Money) -> Optional[Decimal]:
    if annual_saving <= 0:
        return None
    if cost <= 0:
        return Decimal("0.00")
    return (cost / annual_saving * Decimal("12")).quantize(Decimal("0.01"))


def calculate(case: MigrationCase) -> EconomicsResult:
    case.validate()
    gross = sum(
        (
            case.migration_engineering_cost,
            case.partner_services_cost,
            case.internal_labour_cost,
            case.training_cost,
            case.parallel_run_cost,
            case.refactoring_cost,
            case.risk_contingency_cost,
            case.effective_data_movement_cost,
            case.decommissioning_cost,
            case.backup_dr_transition_cost,
            case.security_transition_cost,
            case.support_transition_cost,
        ),
        Decimal("0"),
    )
    received_capital = case.provider_credit_received + case.partner_incentive_received
    cash_cost = gross - received_capital
    # Preserve over-subsidy as evidence in cash cost, but never express it as a negative payback duration.
    status_quo_avoidance = case.status_quo_annual_cost - case.target_annual_cost
    operating_saving = case.current_annual_cost - case.target_annual_cost
    return EconomicsResult(
        gross_switching_cost=gross,
        received_capital=received_capital,
        customer_cash_switching_cost=cash_cost,
        annual_status_quo_avoidance=status_quo_avoidance,
        annual_operating_saving=operating_saving,
        year_one_economic_effect=status_quo_avoidance - gross,
        year_one_customer_cash_effect=status_quo_avoidance - cash_cost,
        economic_payback_months=_payback_months(gross, status_quo_avoidance),
        customer_cash_payback_months=_payback_months(cash_cost, status_quo_avoidance),
    )
