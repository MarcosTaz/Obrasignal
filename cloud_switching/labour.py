from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class ActivityCode(str, Enum):
    INTAKE = "intake"
    ESTATE = "estate"
    BILLING = "billing"
    STATUS_QUO = "status_quo"
    OPTIONS = "options"
    MIGRATION_COST = "migration_cost"
    INCENTIVE = "incentive"
    FORECAST_FREEZE = "forecast_freeze"
    COMPARABILITY = "comparability"
    ACTUALS = "actuals"
    PERFORMANCE = "performance"
    ORACLE_QA = "oracle_qa"
    REPORT = "report"
    REWORK = "rework"


@dataclass(frozen=True)
class LabourEntry:
    activity: ActivityCode
    hours: Decimal
    case_id: str
    note: str = ""

    def validate(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id is required")
        if self.hours <= 0:
            raise ValueError("labour hours must be positive")


@dataclass(frozen=True)
class LabourSummary:
    case_id: str
    total_hours: Decimal
    rework_hours: Decimal
    productive_hours: Decimal
    hours_by_activity: dict[str, Decimal]
    revenue: Decimal | None
    revenue_per_human_hour: Decimal | None


def summarize_labour(entries: list[LabourEntry], *, revenue: Decimal | None = None) -> LabourSummary:
    if not entries:
        raise ValueError("at least one labour entry is required")
    for entry in entries:
        entry.validate()
    case_ids = {entry.case_id for entry in entries}
    if len(case_ids) != 1:
        raise ValueError("labour summary cannot mix cases")
    if revenue is not None and revenue < 0:
        raise ValueError("revenue cannot be negative")

    hours_by_activity: dict[str, Decimal] = {}
    for entry in entries:
        key = entry.activity.value
        hours_by_activity[key] = hours_by_activity.get(key, Decimal("0")) + entry.hours

    total = sum(hours_by_activity.values(), Decimal("0"))
    rework = hours_by_activity.get(ActivityCode.REWORK.value, Decimal("0"))
    productive = total - rework
    rate = None if revenue is None else (revenue / total).quantize(Decimal("0.01"))
    return LabourSummary(
        case_id=next(iter(case_ids)),
        total_hours=total,
        rework_hours=rework,
        productive_hours=productive,
        hours_by_activity=hours_by_activity,
        revenue=revenue,
        revenue_per_human_hour=rate,
    )


def productization_gate(*, median_lifecycle_hours: Decimal, manual_material_field_share: Decimal, outcomes: int) -> str:
    if outcomes < 20:
        return "MEASURE_MORE"
    if not Decimal("0") <= manual_material_field_share <= Decimal("1"):
        raise ValueError("manual material field share must be between 0 and 1")
    if median_lifecycle_hours > Decimal("12") or manual_material_field_share > Decimal("0.40"):
        return "DOWNGRADE_PRODUCTIZATION"
    return "PRODUCTIZATION_ALIVE"
