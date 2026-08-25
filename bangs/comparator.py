from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .costs import CostAssessment
from .evidence import Availability, ConfirmationState
from .money import CurrencyMismatch, Money

class Objective(str, Enum):
    LOWEST_KNOWN_COST = "LOWEST_KNOWN_COST"
    LOWEST_LANDED_COST = "LOWEST_LANDED_COST"
    LOWEST_CASH_OUTLAY = "LOWEST_CASH_OUTLAY"
    SHORTEST_ROUTE = "SHORTEST_ROUTE"
    LOWEST_TRAVEL_TIME = "LOWEST_TRAVEL_TIME"

class ComparisonStatus(str, Enum):
    CONFIRMED_BEST_OBSERVED = "CONFIRMED_BEST_OBSERVED"
    LOWEST_OBSERVED_AVAILABILITY_UNKNOWN = "LOWEST_OBSERVED_AVAILABILITY_UNKNOWN"
    LOWEST_KNOWN_PARTIAL = "LOWEST_KNOWN_PARTIAL"
    NO_COMPARABLE_WINNER = "NO_COMPARABLE_WINNER"
    MULTI_CURRENCY_UNRESOLVED = "MULTI_CURRENCY_UNRESOLVED"
    TRADEOFF = "TRADEOFF"

@dataclass(frozen=True, slots=True)
class CostOption:
    option_id: str
    assessment: CostAssessment
    availability: Availability = Availability.UNKNOWN
    confirmation: ConfirmationState = ConfirmationState.AVAILABILITY_UNKNOWN
    equivalence_key: str | None = None
    travel_time_minutes: Decimal | None = None
    route_distance_km: Decimal | None = None

@dataclass(frozen=True, slots=True)
class ComparisonResult:
    status: ComparisonStatus
    winner_id: str | None
    ordered_option_ids: tuple[str, ...]
    savings_vs_next: Money | None
    notes: tuple[str, ...] = ()


def compare_cost_options(options: tuple[CostOption, ...], *, objective: Objective = Objective.LOWEST_KNOWN_COST) -> ComparisonResult:
    if not options:
        return ComparisonResult(ComparisonStatus.NO_COMPARABLE_WINNER, None, ())
    eq = {o.equivalence_key for o in options if o.equivalence_key is not None}
    if len(eq) > 1:
        return ComparisonResult(ComparisonStatus.NO_COMPARABLE_WINNER, None, tuple(o.option_id for o in options), None, ("EQUIVALENCE_MISMATCH",))
    eligible = [o for o in options if o.availability is not Availability.UNAVAILABLE]
    if objective in {Objective.SHORTEST_ROUTE, Objective.LOWEST_TRAVEL_TIME}:
        attr = "route_distance_km" if objective is Objective.SHORTEST_ROUTE else "travel_time_minutes"
        known = [o for o in eligible if getattr(o, attr) is not None]
        if not known:
            return ComparisonResult(ComparisonStatus.NO_COMPARABLE_WINNER, None, tuple(o.option_id for o in options))
        ordered = sorted(known, key=lambda o: (getattr(o, attr), o.option_id))
        winner = ordered[0]
        status = ComparisonStatus.CONFIRMED_BEST_OBSERVED if winner.availability in {Availability.AVAILABLE, Availability.LIMITED} else ComparisonStatus.LOWEST_OBSERVED_AVAILABILITY_UNKNOWN
        return ComparisonResult(status, winner.option_id, tuple(o.option_id for o in ordered))
    known = [o for o in eligible if o.assessment.known_total is not None]
    if not known:
        return ComparisonResult(ComparisonStatus.NO_COMPARABLE_WINNER, None, tuple(o.option_id for o in options))
    currencies = {o.assessment.known_total.currency for o in known if o.assessment.known_total is not None}
    if len(currencies) > 1:
        return ComparisonResult(ComparisonStatus.MULTI_CURRENCY_UNRESOLVED, None, tuple(o.option_id for o in options), None, ("FX_REQUIRED",))
    ordered = sorted(known, key=lambda o: (o.assessment.known_total.amount, o.option_id))
    winner = ordered[0]
    # A partial or wholly unknown competing cost can invalidate a real cheapest
    # claim. We may still expose the lowest KNOWN subtotal, but never confirm it as
    # economically best until comparable material unknowns are resolved.
    has_unknown_cost = any(
        o.assessment.known_total is None or bool(o.assessment.unknown_components)
        for o in eligible
    )
    if has_unknown_cost:
        return ComparisonResult(
            ComparisonStatus.LOWEST_KNOWN_PARTIAL,
            winner.option_id,
            tuple(o.option_id for o in ordered),
            None,
            ("UNKNOWN_COST_COMPONENTS",),
        )
    savings = None
    if len(ordered) > 1:
        first, second = ordered[0].assessment.known_total, ordered[1].assessment.known_total
        savings = Money(second.amount - first.amount, first.currency)
    confirmed = winner.availability in {Availability.AVAILABLE, Availability.LIMITED} and winner.confirmation is ConfirmationState.AVAILABILITY_CONFIRMED
    status = ComparisonStatus.CONFIRMED_BEST_OBSERVED if confirmed else ComparisonStatus.LOWEST_OBSERVED_AVAILABILITY_UNKNOWN
    return ComparisonResult(status, winner.option_id, tuple(o.option_id for o in ordered), savings)
