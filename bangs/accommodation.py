from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from enum import Enum

from .costs import CostAssessment, CostBasis, CostLine, assess_cost_lines
from .evidence import ConfirmationState, SourceEvidence
from .money import Money

class AccommodationType(str, Enum):
    HOTEL = "HOTEL"
    HOSTEL = "HOSTEL"
    GUESTHOUSE = "GUESTHOUSE"
    APARTMENT = "APARTMENT"
    SERVICED_APARTMENT = "SERVICED_APARTMENT"
    LONG_STAY = "LONG_STAY"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"

class RateBasis(str, Enum):
    ROOM_PER_NIGHT = "ROOM_PER_NIGHT"
    PERSON_PER_NIGHT = "PERSON_PER_NIGHT"
    APARTMENT_PER_NIGHT = "APARTMENT_PER_NIGHT"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, slots=True)
class AccommodationCandidate:
    candidate_id: str
    name: str
    accommodation_type: AccommodationType
    nightly_or_period_rate: Money
    rate_basis: RateBasis
    capacity_per_rate_unit: int | None
    evidence: SourceEvidence
    confirmation: ConfirmationState = ConfirmationState.AVAILABILITY_UNKNOWN
    location: str | None = None
    distance_to_site_km: Decimal | None = None
    travel_time_to_site_minutes: Decimal | None = None
    rooms: int | None = None
    beds: int | None = None
    parking: bool | None = None
    vehicle_access: bool | None = None
    breakfast: bool | None = None
    cancellation_terms: str | None = None

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        name = str(self.name or "").strip()
        if not candidate_id or len(candidate_id) > 180 or not name or len(name) > 300:
            raise ValueError("accommodation candidate id and name are required and bounded")
        if self.location is not None and len(str(self.location)) > 1000:
            raise ValueError("accommodation location too long")
        if self.cancellation_terms is not None and len(str(self.cancellation_terms)) > 4000:
            raise ValueError("cancellation terms too long")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "name", name)
        if self.rate_basis is not RateBasis.UNKNOWN and self.capacity_per_rate_unit is not None and self.capacity_per_rate_unit <= 0:
            raise ValueError("capacity_per_rate_unit must be positive")
        if self.distance_to_site_km is not None and self.distance_to_site_km < 0:
            raise ValueError("distance_to_site_km cannot be negative")
        if self.travel_time_to_site_minutes is not None and self.travel_time_to_site_minutes < 0:
            raise ValueError("travel time cannot be negative")

@dataclass(frozen=True, slots=True)
class AccommodationAssessment:
    candidate_id: str
    crew_size: int
    nights: int
    rate_units_required: int | None
    billing_periods: Decimal | None
    assessment: CostAssessment
    confirmation: ConfirmationState


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def assess_accommodation(candidate: AccommodationCandidate, *, crew_size: int, nights: int, now: datetime) -> AccommodationAssessment:
    if crew_size <= 0 or crew_size > 10000:
        raise ValueError("crew_size must be between 1 and 10000")
    if nights <= 0 or nights > 3660:
        raise ValueError("nights must be between 1 and 3660")
    now = now.astimezone(timezone.utc) if now.tzinfo else (_ for _ in ()).throw(ValueError("now must be timezone-aware"))
    unknowns: list[str] = []
    warnings: list[str] = []
    if candidate.evidence.valid_until and now > candidate.evidence.valid_until:
        warnings.append("RATE_EXPIRED")
        unknowns.append("current_accommodation_rate")
    if candidate.confirmation is ConfirmationState.AVAILABILITY_UNKNOWN:
        warnings.append("AVAILABILITY_UNKNOWN")
    elif candidate.confirmation is ConfirmationState.PRICE_OBSERVED:
        warnings.append("PRICE_OBSERVED_NOT_CONFIRMED_BOOKING")
    basis = candidate.rate_basis
    capacity = candidate.capacity_per_rate_unit
    if basis is RateBasis.UNKNOWN:
        return AccommodationAssessment(candidate.candidate_id, crew_size, nights, None, None, assess_cost_lines((), unknown_components=("rate_basis", *unknowns), warnings=warnings), candidate.confirmation)
    if basis is RateBasis.PERSON_PER_NIGHT:
        rate_units = crew_size
        periods = Decimal(nights)
    else:
        if capacity is None:
            return AccommodationAssessment(candidate.candidate_id, crew_size, nights, None, None, assess_cost_lines((), unknown_components=("occupancy_capacity", *unknowns), warnings=warnings), candidate.confirmation)
        rate_units = _ceil_div(crew_size, capacity)
        if basis in {RateBasis.ROOM_PER_NIGHT, RateBasis.APARTMENT_PER_NIGHT}:
            periods = Decimal(nights)
        elif basis is RateBasis.WEEKLY:
            periods = (Decimal(nights) / Decimal("7")).to_integral_value(rounding=ROUND_CEILING)
        elif basis is RateBasis.MONTHLY:
            periods = (Decimal(nights) / Decimal("30")).to_integral_value(rounding=ROUND_CEILING)
        else:
            raise AssertionError("unhandled rate basis")
    amount = candidate.nightly_or_period_rate.times(Decimal(rate_units) * periods)
    line = CostLine("accommodation", amount, CostBasis.MARKET_OBSERVATION, candidate.evidence)
    return AccommodationAssessment(candidate.candidate_id, crew_size, nights, rate_units, periods, assess_cost_lines((line,), unknown_components=unknowns, warnings=warnings), candidate.confirmation)
