from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence

from .comparability import (
    ComparabilityAssessment,
    ComparabilityGrade,
    ObservationWindow,
    assess_comparability,
)
from .options import OptionComparison, SwitchingOption, compare_options
from .outcome import MigrationOutcomeRecord
from .service import DecisionPackage


@dataclass(frozen=True)
class OutcomeReconciliation:
    migration_cost_variance: Optional[Decimal]
    migration_cost_variance_pct: Optional[Decimal]
    duration_variance_days: Optional[Decimal]
    annual_run_cost_variance: Optional[Decimal]
    annual_run_cost_variance_pct: Optional[Decimal]
    downtime_variance_minutes: Optional[Decimal]
    provider_incentive_variance: Optional[Decimal]
    comparable_run_cost: bool
    comparability_grade: str
    comparability_reasons: tuple[str, ...]
    verified_for_benchmark: bool


@dataclass(frozen=True)
class EconomicAssuranceDelivery:
    decision: DecisionPackage
    options: OptionComparison
    outcome: Optional[OutcomeReconciliation]


def reconcile_outcome(
    record: MigrationOutcomeRecord,
    *,
    pre_run_cost: Decimal,
    pre_window: ObservationWindow,
    post_window: ObservationWindow,
) -> OutcomeReconciliation:
    if record.annual_run_cost.actual is None:
        comparability = ComparabilityAssessment(
            grade=ComparabilityGrade.U,
            comparable=False,
            reasons=("actual annual run cost unavailable",),
            normalized_pre_cost_per_unit=None,
            normalized_post_cost_per_unit=None,
        )
    else:
        comparability = assess_comparability(
            pre_cost=pre_run_cost,
            post_cost=record.annual_run_cost.actual,
            pre=pre_window,
            post=post_window,
        )

    return OutcomeReconciliation(
        migration_cost_variance=record.migration_cost.variance,
        migration_cost_variance_pct=record.migration_cost.variance_pct,
        duration_variance_days=record.duration_days.variance,
        annual_run_cost_variance=record.annual_run_cost.variance,
        annual_run_cost_variance_pct=record.annual_run_cost.variance_pct,
        downtime_variance_minutes=record.downtime_minutes.variance,
        provider_incentive_variance=record.provider_incentive.variance,
        comparable_run_cost=comparability.comparable,
        comparability_grade=comparability.grade.value,
        comparability_reasons=comparability.reasons,
        verified_for_benchmark=record.verified_for_benchmark() and comparability.comparable,
    )


def build_delivery(
    decision: DecisionPackage,
    options: Sequence[SwitchingOption],
    *,
    horizon_years: int = 3,
    outcome_record: Optional[MigrationOutcomeRecord] = None,
    pre_run_cost: Optional[Decimal] = None,
    pre_window: Optional[ObservationWindow] = None,
    post_window: Optional[ObservationWindow] = None,
) -> EconomicAssuranceDelivery:
    comparison = compare_options(options, horizon_years=horizon_years)
    outcome = None
    if outcome_record is not None:
        if pre_run_cost is None or pre_window is None or post_window is None:
            raise ValueError("outcome reconciliation requires pre_run_cost and both observation windows")
        outcome = reconcile_outcome(
            outcome_record,
            pre_run_cost=pre_run_cost,
            pre_window=pre_window,
            post_window=post_window,
        )
    return EconomicAssuranceDelivery(decision=decision, options=comparison, outcome=outcome)
