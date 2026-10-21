from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .evidence import SourceEvidence
from .money import CurrencyMismatch, Money, sum_money

class CostBasis(str, Enum):
    FACT = "FACT"
    QUOTE = "QUOTE"
    MARKET_OBSERVATION = "MARKET_OBSERVATION"
    ESTIMATE = "ESTIMATE"
    ASSUMPTION = "ASSUMPTION"

class CostCompleteness(str, Enum):
    PARTIAL_TOTAL = "PARTIAL_TOTAL"
    COMPLETE_WITHIN_DECLARED_SCOPE = "COMPLETE_WITHIN_DECLARED_SCOPE"
    INSUFFICIENT_FOR_TOTAL = "INSUFFICIENT_FOR_TOTAL"

@dataclass(frozen=True, slots=True)
class CostLine:
    code: str
    amount: Money
    basis: CostBasis
    evidence: SourceEvidence | None = None
    note: str | None = None
    cash_only: bool = False

    def __post_init__(self) -> None:
        code = str(self.code or "").strip().lower()
        if not code or len(code) > 100:
            raise ValueError("cost line code is required")
        object.__setattr__(self, "code", code)

@dataclass(frozen=True, slots=True)
class CostAssessment:
    lines: tuple[CostLine, ...]
    known_total: Money | None
    unknown_components: tuple[str, ...]
    completeness: CostCompleteness
    currencies: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def has_unknowns(self) -> bool:
        return bool(self.unknown_components)


def assess_cost_lines(
    lines: Iterable[CostLine],
    *,
    unknown_components: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> CostAssessment:
    materialized = tuple(lines)
    unknowns = tuple(dict.fromkeys(str(x).strip() for x in unknown_components if str(x).strip()))
    currencies = tuple(sorted({line.amount.currency for line in materialized}))
    warning_list = list(dict.fromkeys(str(x).strip() for x in warnings if str(x).strip()))
    if len(currencies) > 1:
        warning_list.append("MULTI_CURRENCY_UNRESOLVED")
        if "multi_currency_unresolved" not in unknowns:
            unknowns = (*unknowns, "multi_currency_unresolved")
        return CostAssessment(materialized, None, unknowns, CostCompleteness.INSUFFICIENT_FOR_TOTAL, currencies, tuple(warning_list))
    total = sum_money((line.amount for line in materialized), currency=currencies[0] if currencies else None)
    if unknowns:
        completeness = CostCompleteness.PARTIAL_TOTAL if total is not None else CostCompleteness.INSUFFICIENT_FOR_TOTAL
    else:
        completeness = CostCompleteness.COMPLETE_WITHIN_DECLARED_SCOPE if total is not None else CostCompleteness.INSUFFICIENT_FOR_TOTAL
    return CostAssessment(materialized, total, unknowns, completeness, currencies, tuple(warning_list))


def combine_assessments(*assessments: CostAssessment, prefix_unknowns: tuple[str, ...] = ()) -> CostAssessment:
    """Compose already-assessed costs without losing unknowns or warnings."""
    lines: list[CostLine] = []
    unknowns: list[str] = list(prefix_unknowns)
    warnings: list[str] = []
    for assessment in assessments:
        lines.extend(assessment.lines)
        unknowns.extend(assessment.unknown_components)
        warnings.extend(assessment.warnings)
    return assess_cost_lines(lines, unknown_components=unknowns, warnings=warnings)
