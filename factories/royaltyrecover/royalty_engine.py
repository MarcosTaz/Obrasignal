from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, Tuple


ENGINE_VERSION = "0.2.0"


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
class RoyaltyTier:
    lower_bound: Decimal
    rate: Decimal
    upper_bound: Optional[Decimal] = None
    source_clause: Optional[str] = None


@dataclass(frozen=True)
class RoyaltyRule:
    rule_id: str
    basis: str
    rate: Optional[Decimal] = None
    per_unit: Optional[Decimal] = None
    minimum_guarantee: Optional[Decimal] = None
    cap: Optional[Decimal] = None
    floor: Optional[Decimal] = None
    tiers: Tuple[RoyaltyTier, ...] = ()
    sublicense_share: Optional[Decimal] = None
    currency: str = "EUR"
    source_clause: Optional[str] = None
    requires_professional_review: bool = False


@dataclass(frozen=True)
class PeriodInput:
    gross_sales: Optional[Decimal] = None
    units: Optional[Decimal] = None
    permitted_deductions: Optional[Decimal] = None
    sublicense_revenue: Optional[Decimal] = None
    reported_royalty: Optional[Decimal] = None
    paid_royalty: Optional[Decimal] = None
    source_currency: Optional[str] = None
    fx_rate_to_rule_currency: Optional[Decimal] = None
    fx_rate_date: Optional[date] = None
    fx_evidence_id: Optional[str] = None
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
    engine_version: str = ENGINE_VERSION


@dataclass(frozen=True)
class DeadlineResult:
    state: DeadlineState
    days_remaining: Optional[int]
    reason: str


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fail(state: FindingState, data: PeriodInput, reason: str) -> CalculationResult:
    return CalculationResult(
        state, None, data.reported_royalty, data.paid_royalty,
        None, None, None, reason,
    )


def assess_deadline(today: date, deadline: Optional[date], approaching_days: int = 90) -> DeadlineResult:
    if deadline is None:
        return DeadlineResult(DeadlineState.UNKNOWN, None, "No contract-supported deadline is available.")
    days = (deadline - today).days
    if days < 0:
        return DeadlineResult(DeadlineState.EXPIRED, days, "The supplied deadline has passed; no recoverability conclusion is implied.")
    if days <= approaching_days:
        return DeadlineResult(DeadlineState.APPROACHING, days, "The supplied deadline is approaching and should be professionally reviewed.")
    return DeadlineResult(DeadlineState.SAFE, days, "The supplied deadline is outside the configured warning window.")


def _progressive_tier_royalty(base: Decimal, tiers: Tuple[RoyaltyTier, ...]) -> Optional[Decimal]:
    if base < 0 or not tiers:
        return None
    ordered = sorted(tiers, key=lambda tier: tier.lower_bound)
    if ordered[0].lower_bound != 0:
        return None
    total = Decimal("0")
    prior_upper: Optional[Decimal] = None
    for index, tier in enumerate(ordered):
        if not tier.source_clause or tier.rate < 0 or tier.lower_bound < 0:
            return None
        if index and prior_upper != tier.lower_bound:
            return None
        if tier.upper_bound is not None and tier.upper_bound <= tier.lower_bound:
            return None
        if tier.upper_bound is None and index != len(ordered) - 1:
            return None
        upper = tier.upper_bound if tier.upper_bound is not None else base
        taxable = max(Decimal("0"), min(base, upper) - tier.lower_bound)
        total += taxable * tier.rate
        prior_upper = tier.upper_bound
        if base <= upper:
            break
    if ordered[-1].upper_bound is not None and base > ordered[-1].upper_bound:
        return None
    return total


def _convert_base(value: Decimal, rule: RoyaltyRule, data: PeriodInput) -> Optional[Decimal]:
    source_currency = data.source_currency or rule.currency
    if source_currency == rule.currency:
        return value
    if (
        data.fx_rate_to_rule_currency is None
        or data.fx_rate_to_rule_currency <= 0
        or data.fx_rate_date is None
        or not data.fx_evidence_id
    ):
        return None
    return value * data.fx_rate_to_rule_currency


def calculate(rule: RoyaltyRule, data: PeriodInput) -> CalculationResult:
    if not rule.source_clause:
        return _fail(FindingState.UNKNOWN, data, "Missing contractual clause evidence.")
    if rule.requires_professional_review:
        return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "The selected rule depends on professional contract/accounting judgment.")
    if data.conflicting_datasets:
        return _fail(FindingState.NEEDS_DATA, data, "Conflicting source datasets must be reconciled before calculation.")
    if data.duplicate_transactions_detected:
        return _fail(FindingState.NEEDS_DATA, data, "Potential duplicate transactions must be resolved before calculation.")
    if not data.source_data_complete:
        return _fail(FindingState.NEEDS_DATA, data, "Source sales/usage data is incomplete.")

    expected: Optional[Decimal] = None

    if rule.basis in {"PERCENTAGE_GROSS_SALES", "PERCENTAGE_NET_SALES", "TIERED_NET_SALES"}:
        if data.gross_sales is None or data.gross_sales < 0:
            return _fail(FindingState.NEEDS_DATA, data, "Valid gross sales are required.")
        base = data.gross_sales
        if rule.basis != "PERCENTAGE_GROSS_SALES":
            if data.permitted_deductions is None:
                return _fail(FindingState.NEEDS_DATA, data, "Contract-supported permitted deductions are required.")
            if data.permitted_deductions < 0 or data.permitted_deductions > data.gross_sales:
                return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Sales/deduction values are invalid or require interpretation.")
            base -= data.permitted_deductions
        converted = _convert_base(base, rule, data)
        if converted is None:
            return _fail(FindingState.NEEDS_DATA, data, "Currency conversion requires a positive sourced FX rate, rate date and evidence identifier.")
        if rule.basis == "TIERED_NET_SALES":
            expected = _progressive_tier_royalty(converted, rule.tiers)
            if expected is None:
                return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Tier schedule is incomplete, overlapping, gapped, uncited or unsupported.")
        else:
            if rule.rate is None or rule.rate < 0:
                return _fail(FindingState.NEEDS_DATA, data, "A valid contract-supported rate is missing.")
            expected = converted * rule.rate

    elif rule.basis == "PER_UNIT":
        if data.units is None or rule.per_unit is None:
            return _fail(FindingState.NEEDS_DATA, data, "Units or contract-supported per-unit royalty is missing.")
        if data.units < 0 or rule.per_unit < 0:
            return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Negative units/rate require review.")
        expected = data.units * rule.per_unit

    elif rule.basis == "SUBLICENSE_SHARE":
        if data.sublicense_revenue is None or rule.sublicense_share is None:
            return _fail(FindingState.NEEDS_DATA, data, "Sublicense revenue or contract-supported share is missing.")
        if data.sublicense_revenue < 0 or rule.sublicense_share < 0:
            return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Negative sublicense values require review.")
        converted = _convert_base(data.sublicense_revenue, rule, data)
        if converted is None:
            return _fail(FindingState.NEEDS_DATA, data, "Currency conversion requires a positive sourced FX rate, rate date and evidence identifier.")
        expected = converted * rule.sublicense_share

    else:
        return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, f"Unsupported or ambiguous royalty basis: {rule.basis}")

    if rule.floor is not None:
        if rule.floor < 0:
            return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Negative floor requires review.")
        expected = max(expected, rule.floor)
    if rule.minimum_guarantee is not None:
        if rule.minimum_guarantee < 0:
            return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Negative minimum guarantee requires review.")
        expected = max(expected, rule.minimum_guarantee)
    if rule.cap is not None:
        if rule.cap < 0:
            return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Negative cap requires review.")
        if rule.floor is not None and rule.cap < rule.floor:
            return _fail(FindingState.REQUIRES_PROFESSIONAL_REVIEW, data, "Cap is below floor.")
        expected = min(expected, rule.cap)

    expected = _money(expected)
    reported = _money(data.reported_royalty) if data.reported_royalty is not None else None
    paid = _money(data.paid_royalty) if data.paid_royalty is not None else None
    expected_vs_reported = _money(expected - reported) if reported is not None else None
    reported_vs_paid = _money(reported - paid) if reported is not None and paid is not None else None

    if reported is None or paid is None:
        return CalculationResult(
            FindingState.NEEDS_DATA, expected, reported, paid,
            expected_vs_reported, reported_vs_paid, None,
            "Statement or payment evidence is missing.",
        )

    candidate = _money(expected - paid)
    if candidate > 0:
        return CalculationResult(
            FindingState.RECOVERY_CANDIDATE, expected, reported, paid,
            expected_vs_reported, reported_vs_paid, candidate,
            "Deterministic contract/data variance found; human review is required before any claim.",
        )

    return CalculationResult(
        FindingState.NO_DEFENSIBLE_RECOVERY, expected, reported, paid,
        expected_vs_reported, reported_vs_paid, Decimal("0.00"),
        "No positive supported difference exists between expected and paid royalty.",
    )
