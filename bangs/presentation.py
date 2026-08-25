from __future__ import annotations

from dataclasses import dataclass

from .comparator import ComparisonResult
from .true_cost import TrueJobCostAssessment

@dataclass(frozen=True, slots=True)
class ExecutiveBangResult:
    known_cost: dict | None
    total_job_cost_state: str
    unknowns: tuple[str, ...]
    best_observed_options: tuple[str, ...]
    major_cost_drivers: tuple[tuple[str, str], ...]
    major_risks: tuple[str, ...]
    next_information_needed: tuple[str, ...]


def build_executive_result(
    true_cost: TrueJobCostAssessment,
    *,
    comparisons: tuple[ComparisonResult, ...] = (),
    major_risks: tuple[str, ...] = (),
) -> ExecutiveBangResult:
    total = true_cost.assessment.known_total
    category_values = [
        (category.value, money)
        for category, money in true_cost.category_totals
        if money is not None
    ]
    category_currencies = {money.currency for _, money in category_values}
    derived_risks = list(major_risks)
    if len(category_currencies) <= 1:
        category_values.sort(key=lambda x: x[1].amount, reverse=True)
        drivers = tuple((name, f"{money.amount} {money.currency}") for name, money in category_values[:5])
    else:
        # Cross-currency numeric ranking is meaningless without an explicit FX basis.
        drivers = ()
        if "MULTI_CURRENCY_UNRESOLVED" not in derived_risks:
            derived_risks.append("MULTI_CURRENCY_UNRESOLVED")
    winners = tuple(result.winner_id for result in comparisons if result.winner_id)
    state = "COMPLETE_WITHIN_DECLARED_SCOPE" if true_cost.total_job_cost_known else "TOTAL_JOB_COST_UNKNOWN"
    return ExecutiveBangResult(
        known_cost=total.as_dict() if total else None,
        total_job_cost_state=state,
        unknowns=true_cost.assessment.unknown_components,
        best_observed_options=winners,
        major_cost_drivers=drivers,
        major_risks=tuple(derived_risks),
        next_information_needed=true_cost.assessment.unknown_components,
    )
