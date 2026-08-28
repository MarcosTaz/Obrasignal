from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from .baseline import CurrentStateBaseline, MissingMaterialInput
from .domain import EconomicsResult, MigrationCase, calculate


class Decision(str, Enum):
    SWITCH = "switch"
    DO_NOT_SWITCH_NOW = "do_not_switch_now"
    RENEW_TEMPORARILY = "renew_temporarily"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reason: str
    economics: Optional[EconomicsResult]
    baseline_annual_cost: Optional[Decimal]


def decide(
    baseline: CurrentStateBaseline,
    case: MigrationCase,
    *,
    maximum_payback_months: Decimal = Decimal("24"),
) -> DecisionResult:
    if maximum_payback_months <= 0:
        raise ValueError("maximum_payback_months must be positive")

    try:
        baseline_cost = baseline.annual_cost()
    except MissingMaterialInput as exc:
        return DecisionResult(
            decision=Decision.NEEDS_MORE_EVIDENCE,
            reason=str(exc),
            economics=None,
            baseline_annual_cost=None,
        )

    if baseline_cost != case.current_annual_cost:
        return DecisionResult(
            decision=Decision.NEEDS_MORE_EVIDENCE,
            reason="baseline total does not reconcile to migration case current annual cost",
            economics=None,
            baseline_annual_cost=baseline_cost,
        )

    economics = calculate(case)
    if economics.annual_status_quo_avoidance <= 0:
        return DecisionResult(
            decision=Decision.DO_NOT_SWITCH_NOW,
            reason="target run rate does not improve the status-quo annual economics",
            economics=economics,
            baseline_annual_cost=baseline_cost,
        )

    if economics.economic_payback_months is None:
        return DecisionResult(
            decision=Decision.DO_NOT_SWITCH_NOW,
            reason="economic payback cannot be established from the supplied economics",
            economics=economics,
            baseline_annual_cost=baseline_cost,
        )

    if economics.economic_payback_months > maximum_payback_months:
        return DecisionResult(
            decision=Decision.RENEW_TEMPORARILY,
            reason="switching economics are positive but exceed the configured payback gate",
            economics=economics,
            baseline_annual_cost=baseline_cost,
        )

    return DecisionResult(
        decision=Decision.SWITCH,
        reason="switching economics are positive and satisfy the configured payback gate",
        economics=economics,
        baseline_annual_cost=baseline_cost,
    )
