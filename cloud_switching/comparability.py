from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class ComparabilityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    U = "U"


@dataclass(frozen=True)
class ObservationWindow:
    months: int
    workload_units: Optional[Decimal] = None
    service_level: Optional[str] = None

    def validate(self) -> None:
        if self.months <= 0:
            raise ValueError("observation months must be positive")
        if self.workload_units is not None and self.workload_units <= 0:
            raise ValueError("workload units must be positive when supplied")


@dataclass(frozen=True)
class ComparabilityAssessment:
    grade: ComparabilityGrade
    comparable: bool
    reasons: tuple[str, ...]
    normalized_pre_cost_per_unit: Optional[Decimal]
    normalized_post_cost_per_unit: Optional[Decimal]


def assess_comparability(
    *,
    pre_cost: Decimal,
    post_cost: Decimal,
    pre: ObservationWindow,
    post: ObservationWindow,
) -> ComparabilityAssessment:
    pre.validate()
    post.validate()
    if pre_cost < 0 or post_cost < 0:
        raise ValueError("observed costs cannot be negative")

    reasons = []
    if pre.months != post.months:
        reasons.append("observation windows differ")
    if pre.service_level and post.service_level and pre.service_level != post.service_level:
        reasons.append("service level changed")

    pre_unit = None
    post_unit = None
    if pre.workload_units is not None and post.workload_units is not None:
        pre_unit = pre_cost / pre.workload_units
        post_unit = post_cost / post.workload_units
    elif pre.workload_units is None and post.workload_units is None:
        reasons.append("no workload-volume normalization")
    else:
        reasons.append("workload-volume denominator missing on one side")

    if "workload-volume denominator missing on one side" in reasons:
        grade = ComparabilityGrade.U
    elif "service level changed" in reasons:
        grade = ComparabilityGrade.C
    elif pre_unit is not None and post_unit is not None and pre.months == post.months:
        grade = ComparabilityGrade.A
    elif pre.months == post.months:
        grade = ComparabilityGrade.B
    else:
        grade = ComparabilityGrade.C

    return ComparabilityAssessment(
        grade=grade,
        comparable=grade in {ComparabilityGrade.A, ComparabilityGrade.B},
        reasons=tuple(reasons),
        normalized_pre_cost_per_unit=pre_unit,
        normalized_post_cost_per_unit=post_unit,
    )
