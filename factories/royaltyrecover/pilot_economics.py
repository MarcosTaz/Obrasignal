from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass(frozen=True)
class PilotEconomicsInput:
    fixed_fee_revenue: Decimal
    analyst_minutes: int
    reviewer_minutes: int
    normalization_minutes: int
    analyst_hourly_cost: Decimal
    reviewer_hourly_cost: Decimal
    normalization_hourly_cost: Decimal
    partner_direct_cost: Decimal = Decimal("0")
    hosting_direct_cost: Decimal = Decimal("0")
    other_direct_cost: Decimal = Decimal("0")
    agreements_received: int = 0
    agreements_completed: int = 0
    recovery_candidates: int = 0
    no_current_recovery: int = 0
    needs_data_or_review: int = 0
    false_positives_confirmed: int = 0


@dataclass(frozen=True)
class PilotEconomicsResult:
    direct_delivery_cost: Decimal
    gross_profit: Decimal
    gross_margin_ratio: Optional[Decimal]
    direct_cost_ratio: Optional[Decimal]
    completed_cost_per_agreement: Optional[Decimal]
    analyst_hours: Decimal
    reviewer_hours: Decimal
    normalization_hours: Decimal
    commercial_gate_60pct_margin: bool
    zero_false_positive_gate: bool
    portfolio_scaling_evidence_available: bool


def _money(value: Decimal, field: str, allow_zero: bool = True) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise ValueError(f"{field} must be finite and {'positive' if not allow_zero else 'non-negative'}")
    return result


def _count(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _hours(minutes: int) -> Decimal:
    return Decimal(minutes) / Decimal("60")


def calculate_pilot_economics(data: PilotEconomicsInput) -> PilotEconomicsResult:
    revenue = _money(data.fixed_fee_revenue, "fixed_fee_revenue")
    analyst_minutes = _count(data.analyst_minutes, "analyst_minutes")
    reviewer_minutes = _count(data.reviewer_minutes, "reviewer_minutes")
    normalization_minutes = _count(data.normalization_minutes, "normalization_minutes")
    analyst_rate = _money(data.analyst_hourly_cost, "analyst_hourly_cost")
    reviewer_rate = _money(data.reviewer_hourly_cost, "reviewer_hourly_cost")
    normalization_rate = _money(data.normalization_hourly_cost, "normalization_hourly_cost")
    partner_cost = _money(data.partner_direct_cost, "partner_direct_cost")
    hosting_cost = _money(data.hosting_direct_cost, "hosting_direct_cost")
    other_cost = _money(data.other_direct_cost, "other_direct_cost")
    received = _count(data.agreements_received, "agreements_received")
    completed = _count(data.agreements_completed, "agreements_completed")
    candidates = _count(data.recovery_candidates, "recovery_candidates")
    no_recovery = _count(data.no_current_recovery, "no_current_recovery")
    needs_review = _count(data.needs_data_or_review, "needs_data_or_review")
    false_positives = _count(data.false_positives_confirmed, "false_positives_confirmed")

    if completed > received:
        raise ValueError("agreements_completed cannot exceed agreements_received")
    if candidates + no_recovery + needs_review > completed:
        raise ValueError("classified agreement counts cannot exceed agreements_completed")

    analyst_hours = _hours(analyst_minutes)
    reviewer_hours = _hours(reviewer_minutes)
    normalization_hours = _hours(normalization_minutes)
    direct_cost = (
        analyst_hours * analyst_rate
        + reviewer_hours * reviewer_rate
        + normalization_hours * normalization_rate
        + partner_cost + hosting_cost + other_cost
    )
    gross_profit = revenue - direct_cost
    margin = None if revenue == 0 else gross_profit / revenue
    direct_cost_ratio = None if revenue == 0 else direct_cost / revenue
    cost_per_agreement = None if completed == 0 else direct_cost / Decimal(completed)

    return PilotEconomicsResult(
        direct_delivery_cost=direct_cost,
        gross_profit=gross_profit,
        gross_margin_ratio=margin,
        direct_cost_ratio=direct_cost_ratio,
        completed_cost_per_agreement=cost_per_agreement,
        analyst_hours=analyst_hours,
        reviewer_hours=reviewer_hours,
        normalization_hours=normalization_hours,
        commercial_gate_60pct_margin=margin is not None and margin >= Decimal("0.60"),
        zero_false_positive_gate=false_positives == 0,
        portfolio_scaling_evidence_available=completed >= 10,
    )
