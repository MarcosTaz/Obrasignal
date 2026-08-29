from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional


class FindingState(str, Enum):
    NO_DEFENSIBLE_RECOVERY = "NO_DEFENSIBLE_RECOVERY"
    RECOVERY_CANDIDATE = "RECOVERY_CANDIDATE"
    UNKNOWN = "UNKNOWN"
    NEEDS_DATA = "NEEDS_DATA"
    REQUIRES_PROFESSIONAL_REVIEW = "REQUIRES_PROFESSIONAL_REVIEW"


class DeadlineState(str, Enum):
    UNKNOWN = "UNKNOWN"
    SAFE = "SAFE"
    APPROACHING = "APPROACHING"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class RoyaltyRule:
    rule_id: str
    basis: str
    rate: Optional[Decimal] = None
    per_unit: Optional[Decimal] = None
    minimum_guarantee: Optional[Decimal] = None
    currency: str = "EUR"
    source_clause: Optional[str] = None
    requires_professional_review: bool = False


@dataclass(frozen=True)
class PeriodInput:
    gross_sales: Optional[Decimal] = None
    units: Optional[Decimal] = None
    permitted_deductions: Optional[Decimal] = None
    reported_royalty: Optional[Decimal] = None
    paid_royalty: Optional[Decimal] = None
    source_data_complete: bool = True
    duplicate_transactions_detected: bool = False
    conflicting_datasets: bool = False


@dataclass(frozen=True)
class CalculationResult:
    state: FindingState
    expected_royalty: Optional[Decimal]
    reported_royalty: Optional[Decimal]
    paid_royalty: Optional[Decimal]
    variance_expected_vs_reported: Optional[Decimal]
    variance_reported_vs_paid: Optional[Decimal]
    recoverable_candidate: Optional[Decimal]
    reason: str


@dataclass(frozen=True)
class DeadlineResult:
    state: DeadlineState
    days_remaining: Optional[int]
    reason: str


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def assess_deadline(today: date, deadline: Optional[date], approaching_days: int = 90) -> DeadlineResult:
    if deadline is None:
        return DeadlineResult(DeadlineState.UNKNOWN, None, "No contract-supported deadline is available.")
    days = (deadline - today).days
    if days < 0:
        return DeadlineResult(DeadlineState.EXPIRED, days, "The supplied deadline has passed; no recoverability conclusion is implied.")
    if days <= approaching_days:
        return DeadlineResult(DeadlineState.APPROACHING, days, "The supplied deadline is approaching and should be professionally reviewed.")
    return DeadlineResult(DeadlineState.SAFE, days, "The supplied deadline is outside the configured warning window.")


def calculate(rule: RoyaltyRule, data: PeriodInput) -> CalculationResult:
    if not rule.source_clause:
        return CalculationResult(
            FindingState.UNKNOWN, None, data.reported_royalty, data.paid_royalty,
            None, None, None, "Missing contractual clause evidence."
        )

    if rule.requires_professional_review:
        return CalculationResult(
            FindingState.REQUIRES_PROFESSIONAL_REVIEW, None, data.reported_royalty, data.paid_royalty,
            None, None, None, "The selected rule depends on professional contract/accounting judgment."
        )

    if data.conflicting_datasets:
        return CalculationResult(
            FindingState.NEEDS_DATA, None, data.reported_royalty, data.paid_royalty,
            None, None, None, "Conflicting source datasets must be reconciled before calculation."
        )

    if data.duplicate_transactions_detected:
        return CalculationResult(
            FindingState.NEEDS_DATA, None, data.reported_royalty, data.paid_royalty,
            None, None, None, "Potential duplicate transactions must be resolved before calculation."
        )

    if not data.source_data_complete:
        return CalculationResult(
            FindingState.NEEDS_DATA, None, data.reported_royalty, data.paid_royalty,
            None, None, None, "Source sales/usage data is incomplete."
        )

    expected: Optional[Decimal] = None

    if rule.basis == "PERCENTAGE_GROSS_SALES":
        if data.gross_sales is None or rule.rate is None:
            return CalculationResult(
                FindingState.NEEDS_DATA, None, data.reported_royalty, data.paid_royalty,
                None, None, None, "Gross sales or contract-supported rate is missing."
            )
        if data.gross_sales < 0:
            return CalculationResult(
                FindingState.REQUIRES_PROFESSIONAL_REVIEW, None, data.reported_royalty, data.paid_royalty,
                None, None, None, "Negative gross sales require review."
            )
        expected = data.gross_sales * rule.rate

    elif rule.basis == "PERCENTAGE_NET_SALES":
        if data.gross_sales is None or data.permitted_deductions is None or rule.rate is None:
            return CalculationResult(
                FindingState.NEEDS_DATA, None, data.reported_royalty, data.paid_royalty,
                None, None, None, "Gross sales, permitted deductions, or contract-supported rate is missing."
            )
        if data.gross_sales < 0 or data.permitted_deductions < 0 or data.permitted_deductions > data.gross_sales:
            return CalculationResult(
                FindingState.REQUIRES_PROFESSIONAL_REVIEW, None, data.reported_royalty, data.paid_royalty,
                None, None, None, "Sales/deduction values are invalid or require interpretation."
            )
        expected = (data.gross_sales - data.permitted_deductions) * rule.rate

    elif rule.basis == "PER_UNIT":
        if data.units is None or rule.per_unit is None:
            return CalculationResult(
                FindingState.NEEDS_DATA, None, data.reported_royalty, data.paid_royalty,
                None, None, None, "Units or contract-supported per-unit royalty is missing."
            )
        if data.units < 0:
            return CalculationResult(
                FindingState.REQUIRES_PROFESSIONAL_REVIEW, None, data.reported_royalty, data.paid_royalty,
                None, None, None, "Negative units require review."
            )
        expected = data.units * rule.per_unit

    else:
        return CalculationResult(
            FindingState.REQUIRES_PROFESSIONAL_REVIEW, None, data.reported_royalty, data.paid_royalty,
            None, None, None, f"Unsupported or ambiguous royalty basis: {rule.basis}"
        )

    if rule.minimum_guarantee is not None:
        expected = max(expected, rule.minimum_guarantee)

    expected = _money(expected)
    reported = _money(data.reported_royalty) if data.reported_royalty is not None else None
    paid = _money(data.paid_royalty) if data.paid_royalty is not None else None
    expected_vs_reported = _money(expected - reported) if reported is not None else None
    reported_vs_paid = _money(reported - paid) if reported is not None and paid is not None else None

    if reported is None or paid is None:
        return CalculationResult(
            FindingState.NEEDS_DATA, expected, reported, paid,
            expected_vs_reported, reported_vs_paid, None,
            "Statement or payment evidence is missing."
        )

    candidate = _money(expected - paid)
    if candidate > 0:
        return CalculationResult(
            FindingState.RECOVERY_CANDIDATE, expected, reported, paid,
            expected_vs_reported, reported_vs_paid, candidate,
            "Deterministic contract/data variance found; human review is required before any claim."
        )

    return CalculationResult(
        FindingState.NO_DEFENSIBLE_RECOVERY, expected, reported, paid,
        expected_vs_reported, reported_vs_paid, Decimal("0.00"),
        "No positive supported difference exists between expected and paid royalty."
    )
