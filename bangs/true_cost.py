from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .costs import CostAssessment, CostCompleteness, CostLine, assess_cost_lines
from .money import Money

class JobCostCategory(str, Enum):
    DIRECT_KNOWN_COST = "DIRECT_KNOWN_COST"
    MATERIAL_LANDED_COST = "MATERIAL_LANDED_COST"
    EQUIPMENT_COST = "EQUIPMENT_COST"
    MOBILIZATION = "MOBILIZATION"
    TRAVEL = "TRAVEL"
    ACCOMMODATION = "ACCOMMODATION"
    FIELD_EXPENSE = "FIELD_EXPENSE"
    FINANCIAL_COST = "FINANCIAL_COST"
    CONTINGENCY_IF_EXPLICIT = "CONTINGENCY_IF_EXPLICIT"
    OTHER = "OTHER"

@dataclass(frozen=True, slots=True)
class JobCostContribution:
    category: JobCostCategory
    assessment: CostAssessment
    major: bool = True

@dataclass(frozen=True, slots=True)
class TrueJobCostAssessment:
    assessment: CostAssessment
    category_totals: tuple[tuple[JobCostCategory, Money | None], ...]
    total_job_cost_known: bool


def assess_true_job_cost(contributions: tuple[JobCostContribution, ...]) -> TrueJobCostAssessment:
    lines: list[CostLine] = []
    unknowns: list[str] = []
    category_totals = []
    for contribution in contributions:
        a = contribution.assessment
        category_totals.append((contribution.category, a.known_total))
        lines.extend(a.lines)
        if a.unknown_components:
            unknowns.extend(f"{contribution.category.value.lower()}:{x}" for x in a.unknown_components)
        if a.known_total is None and contribution.major:
            unknowns.append(f"{contribution.category.value.lower()}:total")
    aggregate = assess_cost_lines(lines, unknown_components=unknowns)
    total_known = aggregate.completeness is CostCompleteness.COMPLETE_WITHIN_DECLARED_SCOPE
    return TrueJobCostAssessment(aggregate, tuple(category_totals), total_known)
