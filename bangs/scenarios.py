from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .true_cost import JobCostContribution, TrueJobCostAssessment, assess_true_job_cost

class Scenario(str, Enum):
    MINIMUM = "MINIMUM"
    PROBABLE = "PROBABLE"
    PRUDENT = "PRUDENT"

@dataclass(frozen=True, slots=True)
class ScenarioSet:
    minimum: TrueJobCostAssessment
    probable: TrueJobCostAssessment
    prudent: TrueJobCostAssessment


def assess_scenarios(
    *,
    minimum: tuple[JobCostContribution, ...],
    probable: tuple[JobCostContribution, ...],
    prudent: tuple[JobCostContribution, ...],
) -> ScenarioSet:
    return ScenarioSet(
        assess_true_job_cost(minimum),
        assess_true_job_cost(probable),
        assess_true_job_cost(prudent),
    )
