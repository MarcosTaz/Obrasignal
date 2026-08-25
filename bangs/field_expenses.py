from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .costs import CostAssessment, CostBasis, CostLine, assess_cost_lines
from .money import Money

class FieldExpenseKind(str, Enum):
    PER_DIEM = "PER_DIEM"
    PARKING = "PARKING"
    LAUNDRY = "LAUNDRY"
    LOCAL_TRANSPORT = "LOCAL_TRANSPORT"
    CONSUMABLES = "CONSUMABLES"
    WASTE_DISPOSAL = "WASTE_DISPOSAL"
    SITE_WELFARE = "SITE_WELFARE"
    COMMUNICATIONS = "COMMUNICATIONS"
    MISCELLANEOUS = "MISCELLANEOUS"

@dataclass(frozen=True, slots=True)
class FieldExpenseInput:
    kind: FieldExpenseKind
    amount: Money | None
    basis: CostBasis | None
    note: str | None = None


def assess_field_expenses(expenses: tuple[FieldExpenseInput, ...], *, required_kinds: tuple[FieldExpenseKind, ...] = ()) -> CostAssessment:
    by_kind = {item.kind: item for item in expenses}
    lines: list[CostLine] = []
    unknowns: list[str] = []
    for item in expenses:
        if item.amount is None or item.basis is None:
            unknowns.append(item.kind.value.lower())
        else:
            lines.append(CostLine(f"field_{item.kind.value.lower()}", item.amount, item.basis, note=item.note))
    for required in required_kinds:
        if required not in by_kind:
            unknowns.append(required.value.lower())
    return assess_cost_lines(lines, unknown_components=unknowns)


def per_diem_expense(*, rate_per_person_day: Money, crew_size: int, days: int) -> FieldExpenseInput:
    if crew_size <= 0 or days <= 0:
        raise ValueError("crew_size and days must be positive")
    return FieldExpenseInput(
        FieldExpenseKind.PER_DIEM,
        rate_per_person_day.times(Decimal(crew_size * days)),
        CostBasis.ASSUMPTION,
        note="company/user supplied per-diem policy",
    )
