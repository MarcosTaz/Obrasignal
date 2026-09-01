from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

Money = Decimal


@dataclass(frozen=True)
class MigrationWave:
    cutover_month: int
    fraction: Decimal

    def validate(self) -> None:
        if self.cutover_month <= 0:
            raise ValueError("cutover_month must be positive")
        if self.fraction <= 0 or self.fraction > 1:
            raise ValueError("wave fraction must be within (0, 1]")


@dataclass(frozen=True)
class PhasedMigrationPlan:
    source_annual_run_cost: Money
    target_annual_run_cost: Money
    waves: Sequence[MigrationWave]
    decommission_lag_months: int = 0
    renewal_overlap_months: int = 0
    renewal_overlap_monthly_cost: Money = Decimal("0")

    def validate(self) -> None:
        if self.source_annual_run_cost < 0 or self.target_annual_run_cost < 0:
            raise ValueError("run costs cannot be negative")
        if self.decommission_lag_months < 0 or self.renewal_overlap_months < 0:
            raise ValueError("month counts cannot be negative")
        if self.renewal_overlap_monthly_cost < 0:
            raise ValueError("renewal overlap cost cannot be negative")
        if not self.waves:
            raise ValueError("at least one migration wave is required")

        total = Decimal("0")
        last_month = 0
        for wave in self.waves:
            wave.validate()
            if wave.cutover_month < last_month:
                raise ValueError("waves must be ordered by cutover_month")
            last_month = wave.cutover_month
            total += wave.fraction
        if total > 1:
            raise ValueError("cumulative migrated fraction cannot exceed 1")


@dataclass(frozen=True)
class PhasedRunResult:
    months: int
    source_run_cost: Money
    target_run_cost: Money
    renewal_overlap_cost: Money
    total_run_cost: Money
    migrated_fraction_at_end: Decimal


def calculate_phased_run_cost(plan: PhasedMigrationPlan, months: int) -> PhasedRunResult:
    plan.validate()
    if months <= 0:
        raise ValueError("months must be positive")

    source_monthly = plan.source_annual_run_cost / Decimal("12")
    target_monthly = plan.target_annual_run_cost / Decimal("12")
    source_total = Decimal("0")
    target_total = Decimal("0")
    renewal_total = Decimal("0")

    for month in range(1, months + 1):
        migrated = sum(
            (wave.fraction for wave in plan.waves if wave.cutover_month <= month),
            Decimal("0"),
        )
        decommissioned = sum(
            (
                wave.fraction
                for wave in plan.waves
                if wave.cutover_month + plan.decommission_lag_months <= month
            ),
            Decimal("0"),
        )
        source_fraction = Decimal("1") - decommissioned
        target_fraction = migrated

        source_total += source_monthly * source_fraction
        target_total += target_monthly * target_fraction
        if month <= plan.renewal_overlap_months:
            renewal_total += plan.renewal_overlap_monthly_cost

    migrated_end = sum(
        (wave.fraction for wave in plan.waves if wave.cutover_month <= months),
        Decimal("0"),
    )
    return PhasedRunResult(
        months=months,
        source_run_cost=source_total,
        target_run_cost=target_total,
        renewal_overlap_cost=renewal_total,
        total_run_cost=source_total + target_total + renewal_total,
        migrated_fraction_at_end=migrated_end,
    )
