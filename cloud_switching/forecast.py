from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .domain import MigrationCase, calculate


@dataclass(frozen=True)
class FrozenMigrationForecast:
    case_id: str
    source_platform: str
    destination_platform: str
    workload_class: str
    migration_strategy: str
    migration_cost: Decimal
    duration_days: Decimal
    annual_run_cost: Decimal
    downtime_minutes: Decimal
    incentive_total: Decimal
    methodology_version: str

    def validate_against_case(self, case: MigrationCase) -> None:
        if self.case_id != case.case_id:
            raise ValueError("forecast case_id does not match migration case")
        identity = (
            self.source_platform,
            self.destination_platform,
            self.workload_class,
            self.migration_strategy,
            self.methodology_version,
        )
        if any(not str(value).strip() for value in identity):
            raise ValueError("forecast identity and methodology fields are required")
        numeric = (
            self.migration_cost,
            self.duration_days,
            self.annual_run_cost,
            self.downtime_minutes,
            self.incentive_total,
        )
        if any(value < 0 for value in numeric):
            raise ValueError("forecast numeric values cannot be negative")

        economics = calculate(case)
        if self.migration_cost != economics.gross_switching_cost:
            raise ValueError("forecast migration_cost must reconcile to gross switching cost")
        if self.annual_run_cost != case.target_annual_cost:
            raise ValueError("forecast annual_run_cost must reconcile to target annual cost")
        approved_total = case.provider_credit_approved + case.partner_incentive_approved
        if self.incentive_total != approved_total:
            raise ValueError("forecast incentive_total must reconcile to approved incentive total")
