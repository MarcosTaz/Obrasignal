from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .costs import CostAssessment, CostBasis, CostLine, assess_cost_lines
from .evidence import SourceEvidence
from .money import Money, as_decimal

class DistanceBasis(str, Enum):
    ROAD_PROVIDER = "ROAD_PROVIDER"
    STRAIGHT_LINE = "STRAIGHT_LINE"
    USER_INPUT = "USER_INPUT"
    ESTIMATE = "ESTIMATE"

class RouteDirection(str, Enum):
    ONE_WAY = "ONE_WAY"
    ROUND_TRIP = "ROUND_TRIP"

class TravelChargeKind(str, Enum):
    TOLL = "TOLL"
    FERRY = "FERRY"
    FLIGHT = "FLIGHT"
    TRAIN = "TRAIN"
    PARKING = "PARKING"
    OTHER = "OTHER"

@dataclass(frozen=True, slots=True)
class RouteFacts:
    distance_km: Decimal
    travel_time_minutes: Decimal | None
    distance_basis: DistanceBasis
    evidence: SourceEvidence | None = None

    def __post_init__(self) -> None:
        distance = as_decimal(self.distance_km)
        if distance < 0:
            raise ValueError("route distance cannot be negative")
        object.__setattr__(self, "distance_km", distance)
        if self.travel_time_minutes is not None:
            duration = as_decimal(self.travel_time_minutes)
            if duration < 0:
                raise ValueError("route travel time cannot be negative")
            object.__setattr__(self, "travel_time_minutes", duration)

@dataclass(frozen=True, slots=True)
class FuelObservation:
    price_per_litre: Money
    region: str | None
    evidence: SourceEvidence

@dataclass(frozen=True, slots=True)
class VehicleEconomics:
    consumption_l_per_100km: Decimal
    fuel: FuelObservation
    vehicle_cost_per_km: Money | None = None

    def __post_init__(self) -> None:
        consumption = as_decimal(self.consumption_l_per_100km)
        if consumption < 0 or consumption > 100:
            raise ValueError("fuel consumption must be between 0 and 100 l/100km")
        object.__setattr__(self, "consumption_l_per_100km", consumption)

@dataclass(frozen=True, slots=True)
class TravelCharge:
    kind: TravelChargeKind
    amount_per_trip: Money
    evidence: SourceEvidence | None = None
    per_leg: bool = False

@dataclass(frozen=True, slots=True)
class RouteCostAssessment:
    distance_km_total: Decimal
    fuel_litres: Decimal
    assessment: CostAssessment
    direction: RouteDirection
    number_of_trips: int


def assess_route_cost(
    route: RouteFacts,
    vehicle: VehicleEconomics,
    *,
    direction: RouteDirection,
    number_of_trips: int = 1,
    charges: tuple[TravelCharge, ...] = (),
    tolls_known: bool | None = None,
    paid_travel_time_rate_per_hour: Money | None = None,
    crew_size: int | None = None,
    travel_time_paid: bool | None = None,
) -> RouteCostAssessment:
    if number_of_trips <= 0 or number_of_trips > 10000:
        raise ValueError("number_of_trips must be between 1 and 10000")
    factor = Decimal("2") if direction is RouteDirection.ROUND_TRIP else Decimal("1")
    distance_total = route.distance_km * factor * number_of_trips
    litres = distance_total * vehicle.consumption_l_per_100km / Decimal("100")
    lines = [CostLine("fuel", vehicle.fuel.price_per_litre.times(litres), CostBasis.MARKET_OBSERVATION, vehicle.fuel.evidence)]
    if vehicle.vehicle_cost_per_km is not None:
        lines.append(CostLine("vehicle_distance_cost", vehicle.vehicle_cost_per_km.times(distance_total), CostBasis.ASSUMPTION))
    for charge in charges:
        charge_factor = number_of_trips * (2 if direction is RouteDirection.ROUND_TRIP and charge.per_leg else 1)
        lines.append(CostLine(f"travel_{charge.kind.value.lower()}", charge.amount_per_trip.times(charge_factor), CostBasis.MARKET_OBSERVATION, charge.evidence))
    unknowns: list[str] = []
    # Missing toll information is UNKNOWN, not an implicit zero. Callers/providers
    # must explicitly assert True when the route has no tolls or all tolls are known.
    if tolls_known is not True:
        unknowns.append("tolls")
    if travel_time_paid is True:
        if paid_travel_time_rate_per_hour is None or crew_size is None:
            unknowns.append("paid_travel_time")
        elif crew_size <= 0:
            raise ValueError("crew_size must be positive")
        elif route.travel_time_minutes is None:
            unknowns.append("route_travel_time")
        else:
            hours = route.travel_time_minutes / Decimal("60") * factor * number_of_trips * crew_size
            lines.append(CostLine("paid_travel_time", paid_travel_time_rate_per_hour.times(hours), CostBasis.ASSUMPTION))
    warnings = []
    if route.distance_basis is DistanceBasis.STRAIGHT_LINE:
        warnings.append("STRAIGHT_LINE_DISTANCE_NOT_ROAD_DISTANCE")
    return RouteCostAssessment(distance_total, litres, assess_cost_lines(lines, unknown_components=unknowns, warnings=warnings), direction, number_of_trips)
