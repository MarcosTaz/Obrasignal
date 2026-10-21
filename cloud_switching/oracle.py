from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .domain import MigrationCase

Money = Decimal


@dataclass(frozen=True)
class OracleResult:
    gross_switching_cost: Money
    received_capital: Money
    customer_cash_switching_cost: Money
    annual_status_quo_avoidance: Money
    economic_payback_months: Optional[Decimal]
    customer_cash_payback_months: Optional[Decimal]


def _oracle_payback(cost: Money, annual_avoidance: Money) -> Optional[Decimal]:
    if annual_avoidance <= 0:
        return None
    if cost <= 0:
        return Decimal("0.00")
    months = Decimal("12") * cost / annual_avoidance
    return months.quantize(Decimal("0.01"))


def oracle_calculate(case: MigrationCase) -> OracleResult:
    case.validate()
    cost_components = [
        case.migration_engineering_cost,
        case.partner_services_cost,
        case.internal_labour_cost,
        case.training_cost,
        case.parallel_run_cost,
        case.refactoring_cost,
        case.risk_contingency_cost,
    ]
    gross = Decimal("0")
    for component in cost_components:
        gross += component

    capital = case.provider_credit_received + case.partner_incentive_received
    cash = gross - capital
    annual_avoidance = case.status_quo_annual_cost - case.target_annual_cost

    return OracleResult(
        gross_switching_cost=gross,
        received_capital=capital,
        customer_cash_switching_cost=cash,
        annual_status_quo_avoidance=annual_avoidance,
        economic_payback_months=_oracle_payback(gross, annual_avoidance),
        customer_cash_payback_months=_oracle_payback(cash, annual_avoidance),
    )
