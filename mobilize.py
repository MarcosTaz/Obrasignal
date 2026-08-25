"""Deterministic mobilization economics for ObraSignal.

MOBILIZE answers how to move a crew to a project at the best total-economic
configuration. It deliberately has no network, database or LLM dependency so
it can be replayed, shadow-tested and replaced behind the stable v1 contract.

Money-bearing calculations are Decimal-backed. Missing availability and cost
inputs fail closed; they are never translated into zero cost or availability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, getcontext
from math import ceil
from typing import Any, Literal

getcontext().prec = 50

EvidenceQuality = Literal["LIVE", "QUOTED", "RECENT", "ESTIMATED", "UNKNOWN"]
ScenarioKind = Literal["DAILY_COMMUTE", "ACCOMMODATION", "WEEKDAY_HYBRID"]
VehicleMode = Literal["OWN", "RENTAL"]
AvailabilityState = Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]

CONTRACT_VERSION = "mobilize.v1"
POLICY_VERSION = "mobilize-policy-v1"
_ALLOWED_QUALITIES = frozenset({"LIVE", "QUOTED", "RECENT", "ESTIMATED", "UNKNOWN"})
_ALLOWED_AVAILABILITY = frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"})
_ZERO = Decimal("0")


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must contain finite non-negative numbers")
    try:
        converted = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} must contain finite non-negative numbers") from exc
    if not converted.is_finite() or converted < 0:
        raise ValueError(f"{name} must contain finite non-negative numbers")
    return converted


def _availability(value: bool | str | None, name: str) -> AvailabilityState:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, bool):
        return "AVAILABLE" if value else "UNAVAILABLE"
    normalized = str(value).strip().upper()
    if normalized not in _ALLOWED_AVAILABILITY:
        raise ValueError(f"{name} must be AVAILABLE, UNAVAILABLE or UNKNOWN")
    return normalized  # type: ignore[return-value]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


@dataclass(frozen=True)
class RangeInput:
    """Auditable Decimal interval; unknown values remain unknown."""

    minimum: Decimal | int | float | str | None = None
    probable: Decimal | int | float | str | None = None
    prudent: Decimal | int | float | str | None = None
    quality: EvidenceQuality = "UNKNOWN"
    source: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        values = (self.minimum, self.probable, self.prudent)
        if any(value is not None for value in values):
            converted = tuple(_decimal(value, "RangeInput") if value is not None else None for value in values)
            object.__setattr__(self, "minimum", converted[0])
            object.__setattr__(self, "probable", converted[1])
            object.__setattr__(self, "prudent", converted[2])

    @classmethod
    def scalar(
        cls,
        value: Decimal | int | float | str,
        *,
        quality: EvidenceQuality = "ESTIMATED",
        source: str | None = None,
        observed_at: str | None = None,
    ) -> "RangeInput":
        return cls(value, value, value, quality, source, observed_at)

    @property
    def known(self) -> bool:
        return self.minimum is not None and self.probable is not None and self.prudent is not None

    def validate(self, name: str) -> None:
        if self.quality not in _ALLOWED_QUALITIES:
            raise ValueError(f"{name} has unsupported evidence quality: {self.quality}")
        values = (self.minimum, self.probable, self.prudent)
        present = [value is not None for value in values]
        if any(present) and not all(present):
            raise ValueError(f"{name} must provide minimum, probable and prudent together")
        if not any(present):
            if self.quality != "UNKNOWN":
                raise ValueError(f"{name} without values must use UNKNOWN quality")
            return
        converted = tuple(_decimal(value, name) for value in values)
        if not (converted[0] <= converted[1] <= converted[2]):
            raise ValueError(f"{name} must satisfy minimum <= probable <= prudent")
        if self.quality == "UNKNOWN":
            raise ValueError(f"{name} with values cannot use UNKNOWN quality")


@dataclass(frozen=True)
class MobilizationContext:
    workers: int
    working_days: int
    distance_km_one_way: RangeInput
    travel_hours_one_way: RangeInput = field(default_factory=RangeInput)
    working_days_per_week: int = 5
    vehicle_seats: int = 5
    own_vehicles_available: int | None = None
    rental_available: bool | AvailabilityState | None = True
    hotel_available: bool | AvailabilityState | None = None
    local_transport_km_per_workday: RangeInput = field(
        default_factory=lambda: RangeInput.scalar(
            0,
            quality="ESTIMATED",
            source="explicit default: site-local transport not supplied",
        )
    )
    currency: str = "EUR"


@dataclass(frozen=True)
class MobilizePolicy:
    """Replaceable regional/company policy; defaults never claim live prices."""

    currency: str = "EUR"
    fuel_price_per_litre: RangeInput = field(default_factory=RangeInput)
    own_vehicle_consumption_l_per_100km: RangeInput = field(default_factory=RangeInput)
    own_vehicle_cost_per_km: RangeInput = field(default_factory=RangeInput)
    rental_vehicle_daily_cost: RangeInput = field(default_factory=RangeInput)
    rental_vehicle_consumption_l_per_100km: RangeInput = field(default_factory=RangeInput)
    tolls_per_vehicle_round_trip: RangeInput = field(default_factory=RangeInput)
    parking_per_vehicle_workday: RangeInput = field(default_factory=RangeInput)
    accommodation_per_worker_night: RangeInput = field(default_factory=RangeInput)
    per_diem_per_worker_day: RangeInput = field(default_factory=RangeInput)
    productive_hour_value_per_worker: RangeInput = field(default_factory=RangeInput)
    maximum_daily_travel_hours: Decimal | int | float | str | None = None
    fatigue_risk_travel_hours: Decimal | int | float | str | None = None
    near_cost_ratio: Decimal | int | float | str = Decimal("1.10")
    material_travel_reduction_hours: Decimal | int | float | str = Decimal("1.0")
    policy_version: str = POLICY_VERSION

    def __post_init__(self) -> None:
        for name in (
            "maximum_daily_travel_hours",
            "fatigue_risk_travel_hours",
            "near_cost_ratio",
            "material_travel_reduction_hours",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _decimal(value, name))


@dataclass(frozen=True)
class CostRange:
    minimum: Decimal
    probable: Decimal
    prudent: Decimal
    currency: str


@dataclass(frozen=True)
class ScenarioAssessment:
    scenario: str
    strategy: ScenarioKind
    vehicle_mode: VehicleMode
    available: bool
    availability_state: AvailabilityState
    comparable: bool
    estimated_cost: Decimal | None
    minimum_cost: Decimal | None
    probable_cost: Decimal | None
    prudent_cost: Decimal | None
    direct_cost: CostRange | None
    productivity_cost: CostRange | None
    cost_per_worker: Decimal | None
    cost_per_day: Decimal | None
    travel_hours: CostRange | None
    non_productive_hours: CostRange | None
    productivity_impact: str
    operational_risks: tuple[str, ...]
    assumptions: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    confidence: int
    evidence: tuple[dict, ...]
    warnings: tuple[str, ...]
    metrics: dict


@dataclass(frozen=True)
class MobilizationAssessment:
    contract_version: str
    policy_version: str
    currency: str
    recommended_scenario: str
    alternative_scenarios: tuple[ScenarioAssessment, ...]
    estimated_cost: Decimal | None
    minimum_cost: Decimal | None
    probable_cost: Decimal | None
    prudent_cost: Decimal | None
    cost_per_worker: Decimal | None
    cost_per_day: Decimal | None
    travel_hours: CostRange | None
    non_productive_hours: CostRange | None
    productivity_impact: str
    operational_risks: tuple[str, ...]
    assumptions: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    confidence: int
    evidence: tuple[dict, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return _json_safe(asdict(self))


def _radd(left: tuple[Decimal, Decimal, Decimal], right: tuple[Decimal, Decimal, Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def _rmul(
    left: tuple[Decimal, Decimal, Decimal],
    right: tuple[Decimal, Decimal, Decimal] | Decimal | int,
) -> tuple[Decimal, Decimal, Decimal]:
    if isinstance(right, tuple):
        return tuple(a * b for a, b in zip(left, right))  # type: ignore[return-value]
    factor = right if isinstance(right, Decimal) else Decimal(right)
    return tuple(value * factor for value in left)  # type: ignore[return-value]


def _vals(value: RangeInput, name: str, missing: list[str]) -> tuple[Decimal, Decimal, Decimal]:
    if value.known:
        return (value.minimum, value.probable, value.prudent)  # type: ignore[return-value]
    if name not in missing:
        missing.append(name)
    return (_ZERO, _ZERO, _ZERO)


def _cost_range(values: tuple[Decimal, Decimal, Decimal], currency: str) -> CostRange:
    return CostRange(*values, currency=currency)


def _evidence(name: str, value: RangeInput) -> dict:
    state = (
        "UNKNOWN"
        if not value.known
        else "ASSUMED"
        if (value.source or "").startswith("explicit default:")
        else "KNOWN"
        if value.quality in {"LIVE", "QUOTED"}
        else "ESTIMATED"
    )
    return {
        "input": name,
        "state": state,
        "quality": value.quality,
        "minimum": value.minimum,
        "probable": value.probable,
        "prudent": value.prudent,
        "source": value.source,
        "observed_at": value.observed_at,
    }


def _validate_number(name: str, value: Decimal | int | float | str | None, *, minimum: Decimal = _ZERO) -> None:
    if value is None:
        return
    converted = _decimal(value, name)
    if converted < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _validate(context: MobilizationContext, policy: MobilizePolicy) -> None:
    if isinstance(context.workers, bool) or not isinstance(context.workers, int) or context.workers <= 0:
        raise ValueError("workers must be a positive integer")
    if isinstance(context.working_days, bool) or not isinstance(context.working_days, int) or context.working_days <= 0:
        raise ValueError("working_days must be a positive integer")
    if (
        isinstance(context.working_days_per_week, bool)
        or not isinstance(context.working_days_per_week, int)
        or context.working_days_per_week <= 0
        or context.working_days_per_week > 7
    ):
        raise ValueError("working_days_per_week must be an integer between 1 and 7")
    if isinstance(context.vehicle_seats, bool) or not isinstance(context.vehicle_seats, int) or context.vehicle_seats <= 0:
        raise ValueError("vehicle_seats must be a positive integer")
    if context.own_vehicles_available is not None and (
        isinstance(context.own_vehicles_available, bool)
        or not isinstance(context.own_vehicles_available, int)
        or context.own_vehicles_available < 0
    ):
        raise ValueError("own_vehicles_available must be a non-negative integer when supplied")
    _availability(context.rental_available, "rental_available")
    _availability(context.hotel_available, "hotel_available")
    if not isinstance(context.currency, str) or not isinstance(policy.currency, str):
        raise ValueError("currency is required")
    if not context.currency.strip() or not policy.currency.strip():
        raise ValueError("currency is required")
    if context.currency.strip().upper() != policy.currency.strip().upper():
        raise ValueError("context and policy currency must match; FX conversion is outside Mobilize V1")

    _validate_number("maximum_daily_travel_hours", policy.maximum_daily_travel_hours)
    _validate_number("fatigue_risk_travel_hours", policy.fatigue_risk_travel_hours)
    _validate_number("near_cost_ratio", policy.near_cost_ratio, minimum=Decimal("1"))
    _validate_number("material_travel_reduction_hours", policy.material_travel_reduction_hours)

    for name, value in (
        ("distance_km_one_way", context.distance_km_one_way),
        ("travel_hours_one_way", context.travel_hours_one_way),
        ("local_transport_km_per_workday", context.local_transport_km_per_workday),
        ("fuel_price_per_litre", policy.fuel_price_per_litre),
        ("own_vehicle_consumption_l_per_100km", policy.own_vehicle_consumption_l_per_100km),
        ("own_vehicle_cost_per_km", policy.own_vehicle_cost_per_km),
        ("rental_vehicle_daily_cost", policy.rental_vehicle_daily_cost),
        ("rental_vehicle_consumption_l_per_100km", policy.rental_vehicle_consumption_l_per_100km),
        ("tolls_per_vehicle_round_trip", policy.tolls_per_vehicle_round_trip),
        ("parking_per_vehicle_workday", policy.parking_per_vehicle_workday),
        ("accommodation_per_worker_night", policy.accommodation_per_worker_night),
        ("per_diem_per_worker_day", policy.per_diem_per_worker_day),
        ("productive_hour_value_per_worker", policy.productive_hour_value_per_worker),
    ):
        if not isinstance(value, RangeInput):
            raise ValueError(f"{name} must be a RangeInput")
        value.validate(name)


def _confidence(evidence: list[dict], missing: list[str], assumptions: list[str], comparable: bool) -> int:
    if not comparable:
        return 0
    score = 100
    penalties = {"LIVE": 0, "QUOTED": 2, "RECENT": 6, "ESTIMATED": 12, "UNKNOWN": 18}
    material = [item for item in evidence if item["input"] != "local_transport_km_per_workday"]
    if material:
        score -= round(sum(penalties[item["quality"]] for item in material) / len(material))
    score -= min(35, len(missing) * 7)
    score -= min(20, len(assumptions) * 4)
    return max(0, min(100, score))


def _scenario(context: MobilizationContext, policy: MobilizePolicy, strategy: ScenarioKind, mode: VehicleMode) -> ScenarioAssessment:
    workers = context.workers
    vehicles = ceil(workers / context.vehicle_seats)
    weeks = ceil(context.working_days / context.working_days_per_week)
    final_week_days = context.working_days - (weeks - 1) * context.working_days_per_week
    calendar_days = max(context.working_days, (weeks - 1) * 7 + final_week_days)

    assumptions: list[str] = []
    missing: list[str] = []
    risks: list[str] = []
    warnings: list[str] = []
    evidence: list[dict] = []

    if mode == "OWN":
        if context.own_vehicles_available is None:
            vehicle_availability: AvailabilityState = "UNKNOWN"
        elif context.own_vehicles_available >= vehicles:
            vehicle_availability = "AVAILABLE"
        else:
            vehicle_availability = "UNAVAILABLE"
    else:
        vehicle_availability = _availability(context.rental_available, "rental_available")

    hotel_availability: AvailabilityState = "AVAILABLE"
    if strategy in {"ACCOMMODATION", "WEEKDAY_HYBRID"}:
        hotel_availability = _availability(context.hotel_available, "hotel_available")

    if vehicle_availability == "UNAVAILABLE" or hotel_availability == "UNAVAILABLE":
        availability_state: AvailabilityState = "UNAVAILABLE"
    elif vehicle_availability == "UNKNOWN" or hotel_availability == "UNKNOWN":
        availability_state = "UNKNOWN"
    else:
        availability_state = "AVAILABLE"
    available = availability_state == "AVAILABLE"

    if vehicle_availability == "UNKNOWN":
        missing.append("own_vehicles_available" if mode == "OWN" else "rental_available")
    elif vehicle_availability == "UNAVAILABLE":
        warnings.append("insufficient own vehicles for crew size" if mode == "OWN" else "rental vehicle unavailable")

    if strategy in {"ACCOMMODATION", "WEEKDAY_HYBRID"}:
        if hotel_availability == "UNKNOWN":
            missing.append("hotel_available")
        elif hotel_availability == "UNAVAILABLE":
            warnings.append("accommodation unavailable")

    if mode == "RENTAL":
        assumptions.append(
            "rental vehicle is modeled on the same base/site travel pattern; local-only pickup/crew transfer is not modeled in V1"
        )

    if strategy == "DAILY_COMMUTE":
        base_round_trips = context.working_days
        lodging_nights = 0
        rental_days = context.working_days
    elif strategy == "WEEKDAY_HYBRID":
        base_round_trips = weeks
        lodging_nights = max(0, context.working_days - weeks)
        rental_days = context.working_days
        assumptions.append("weekday hybrid groups workdays into working weeks and uses one base round-trip per week")
    else:
        base_round_trips = 1
        lodging_nights = max(0, calendar_days - 1)
        rental_days = calendar_days
        assumptions.append("continuous accommodation spans the inferred calendar duration between first and last workday")

    distance = _vals(context.distance_km_one_way, "distance_km_one_way", missing)
    evidence.append(_evidence("distance_km_one_way", context.distance_km_one_way))
    local_distance = _vals(context.local_transport_km_per_workday, "local_transport_km_per_workday", missing)
    evidence.append(_evidence("local_transport_km_per_workday", context.local_transport_km_per_workday))

    base_km = _rmul(distance, 2 * base_round_trips * vehicles)
    local_km = (_ZERO, _ZERO, _ZERO) if strategy == "DAILY_COMMUTE" else _rmul(local_distance, context.working_days * vehicles)
    total_vehicle_km = _radd(base_km, local_km)

    travel_time = _vals(context.travel_hours_one_way, "travel_hours_one_way", missing)
    evidence.append(_evidence("travel_hours_one_way", context.travel_hours_one_way))
    crew_travel_hours = _rmul(travel_time, 2 * base_round_trips * workers)

    direct = (_ZERO, _ZERO, _ZERO)
    comparable = available and context.distance_km_one_way.known

    consumption_input = policy.own_vehicle_consumption_l_per_100km if mode == "OWN" else policy.rental_vehicle_consumption_l_per_100km
    consumption_name = "own_vehicle_consumption_l_per_100km" if mode == "OWN" else "rental_vehicle_consumption_l_per_100km"
    consumption = _vals(consumption_input, consumption_name, missing)
    fuel_price = _vals(policy.fuel_price_per_litre, "fuel_price_per_litre", missing)
    evidence.extend([_evidence(consumption_name, consumption_input), _evidence("fuel_price_per_litre", policy.fuel_price_per_litre)])
    if context.distance_km_one_way.known and context.distance_km_one_way.prudent > _ZERO:  # type: ignore[operator]
        if not consumption_input.known or not policy.fuel_price_per_litre.known:
            comparable = False
    if consumption_input.known and policy.fuel_price_per_litre.known:
        litres = _rmul(total_vehicle_km, tuple(value / Decimal("100") for value in consumption))
        direct = _radd(direct, _rmul(litres, fuel_price))

    if mode == "OWN":
        wear = _vals(policy.own_vehicle_cost_per_km, "own_vehicle_cost_per_km", missing)
        evidence.append(_evidence("own_vehicle_cost_per_km", policy.own_vehicle_cost_per_km))
        if policy.own_vehicle_cost_per_km.known:
            direct = _radd(direct, _rmul(total_vehicle_km, wear))
        elif context.distance_km_one_way.known and context.distance_km_one_way.prudent > _ZERO:  # type: ignore[operator]
            comparable = False
    else:
        rental = _vals(policy.rental_vehicle_daily_cost, "rental_vehicle_daily_cost", missing)
        evidence.append(_evidence("rental_vehicle_daily_cost", policy.rental_vehicle_daily_cost))
        if policy.rental_vehicle_daily_cost.known:
            direct = _radd(direct, _rmul(rental, rental_days * vehicles))
        else:
            comparable = False

    tolls = _vals(policy.tolls_per_vehicle_round_trip, "tolls_per_vehicle_round_trip", missing)
    parking = _vals(policy.parking_per_vehicle_workday, "parking_per_vehicle_workday", missing)
    evidence.extend([_evidence("tolls_per_vehicle_round_trip", policy.tolls_per_vehicle_round_trip), _evidence("parking_per_vehicle_workday", policy.parking_per_vehicle_workday)])
    if policy.tolls_per_vehicle_round_trip.known:
        direct = _radd(direct, _rmul(tolls, base_round_trips * vehicles))
    if policy.parking_per_vehicle_workday.known:
        direct = _radd(direct, _rmul(parking, context.working_days * vehicles))

    if strategy in {"ACCOMMODATION", "WEEKDAY_HYBRID"}:
        hotel = _vals(policy.accommodation_per_worker_night, "accommodation_per_worker_night", missing)
        evidence.append(_evidence("accommodation_per_worker_night", policy.accommodation_per_worker_night))
        if policy.accommodation_per_worker_night.known:
            direct = _radd(direct, _rmul(hotel, lodging_nights * workers))
        else:
            comparable = False
        per_diem = _vals(policy.per_diem_per_worker_day, "per_diem_per_worker_day", missing)
        evidence.append(_evidence("per_diem_per_worker_day", policy.per_diem_per_worker_day))
        if policy.per_diem_per_worker_day.known:
            direct = _radd(direct, _rmul(per_diem, context.working_days * workers))

    productivity_cost_values = (_ZERO, _ZERO, _ZERO)
    productive_value = _vals(policy.productive_hour_value_per_worker, "productive_hour_value_per_worker", missing)
    evidence.append(_evidence("productive_hour_value_per_worker", policy.productive_hour_value_per_worker))
    if context.travel_hours_one_way.known and policy.productive_hour_value_per_worker.known:
        productivity_cost_values = _rmul(crew_travel_hours, productive_value)

    total = _radd(direct, productivity_cost_values)
    probable_daily_travel = context.travel_hours_one_way.probable * 2 if context.travel_hours_one_way.known else None  # type: ignore[operator]
    if strategy == "DAILY_COMMUTE" and probable_daily_travel is not None:
        if policy.maximum_daily_travel_hours is not None and probable_daily_travel > policy.maximum_daily_travel_hours:
            risks.append("daily travel exceeds configured maximum travel-time policy")
        if policy.fatigue_risk_travel_hours is not None and probable_daily_travel >= policy.fatigue_risk_travel_hours:
            risks.append("daily travel reaches configured fatigue-risk threshold")
    if not context.travel_hours_one_way.known:
        warnings.append("travel-time productivity and fatigue exposure cannot be quantified")

    if not comparable:
        total_cost = None
        direct_cost = _cost_range(direct, context.currency) if available else None
        productivity_cost = None
    else:
        total_cost = _cost_range(total, context.currency)
        direct_cost = _cost_range(direct, context.currency)
        productivity_cost = _cost_range(productivity_cost_values, context.currency) if policy.productive_hour_value_per_worker.known and context.travel_hours_one_way.known else None

    if missing:
        warnings.append("reported cost excludes unknown components: " + ", ".join(sorted(set(missing))))

    if not policy.productive_hour_value_per_worker.known:
        productivity_impact = "UNKNOWN — non-productive travel hours are shown but not monetized"
    elif context.travel_hours_one_way.known:
        productivity_impact = f"MONETIZED — probable non-productive crew travel {crew_travel_hours[1]:.2f} h"
    else:
        productivity_impact = "UNKNOWN — travel time unavailable"

    confidence = _confidence(evidence, missing, assumptions, comparable)
    probable = total_cost.probable if total_cost else None
    return ScenarioAssessment(
        scenario=f"{strategy.lower()}_{mode.lower()}",
        strategy=strategy,
        vehicle_mode=mode,
        available=available,
        availability_state=availability_state,
        comparable=comparable,
        estimated_cost=probable,
        minimum_cost=total_cost.minimum if total_cost else None,
        probable_cost=probable,
        prudent_cost=total_cost.prudent if total_cost else None,
        direct_cost=direct_cost,
        productivity_cost=productivity_cost,
        cost_per_worker=probable / Decimal(workers) if probable is not None else None,
        cost_per_day=probable / Decimal(context.working_days) if probable is not None else None,
        travel_hours=_cost_range(crew_travel_hours, "hours") if context.travel_hours_one_way.known else None,
        non_productive_hours=_cost_range(crew_travel_hours, "hours") if context.travel_hours_one_way.known else None,
        productivity_impact=productivity_impact,
        operational_risks=tuple(risks),
        assumptions=tuple(assumptions),
        missing_inputs=tuple(sorted(set(missing))),
        confidence=confidence,
        evidence=tuple(evidence),
        warnings=tuple(warnings),
        metrics={
            "workers": workers,
            "vehicles_required": vehicles,
            "base_round_trips": base_round_trips,
            "lodging_nights_per_worker": lodging_nights,
            "rental_days_per_vehicle": rental_days if mode == "RENTAL" else 0,
            "total_vehicle_km": {"minimum": total_vehicle_km[0], "probable": total_vehicle_km[1], "prudent": total_vehicle_km[2]},
        },
    )


def _choose(scenarios: list[ScenarioAssessment], policy: MobilizePolicy) -> tuple[str, str | None]:
    candidates = [scenario for scenario in scenarios if scenario.available and scenario.comparable and scenario.probable_cost is not None]
    if not candidates:
        return "NO CLEAR WINNER", "no scenario has enough essential cost inputs for a defensible comparison"
    candidates.sort(key=lambda scenario: (scenario.probable_cost, scenario.prudent_cost is None, scenario.prudent_cost or _ZERO, scenario.scenario))
    best = candidates[0]
    if len(candidates) == 1:
        return best.scenario, None
    second = candidates[1]
    overlap = best.prudent_cost is not None and second.minimum_cost is not None and best.prudent_cost >= second.minimum_cost
    if overlap:
        if best.travel_hours and second.travel_hours:
            lower_travel = min((best, second), key=lambda scenario: (scenario.travel_hours is None, scenario.travel_hours.probable if scenario.travel_hours else _ZERO))
            higher_travel = second if lower_travel is best else best
            travel_reduction = higher_travel.travel_hours.probable - lower_travel.travel_hours.probable if higher_travel.travel_hours and lower_travel.travel_hours else _ZERO
            if travel_reduction >= policy.material_travel_reduction_hours and lower_travel.probable_cost <= best.probable_cost * policy.near_cost_ratio:
                return lower_travel.scenario, "overlapping cost ranges; selected policy-defined near-cost option with materially lower travel exposure"
        return "NO CLEAR WINNER", "leading scenario cost ranges overlap; sensitivity is material"
    return best.scenario, None


class Mobilize:
    """Stable v1 capability contract."""

    @staticmethod
    def evaluate(context: MobilizationContext, policy: MobilizePolicy) -> MobilizationAssessment:
        _validate(context, policy)
        scenarios = [_scenario(context, policy, strategy, mode) for strategy in ("DAILY_COMMUTE", "ACCOMMODATION", "WEEKDAY_HYBRID") for mode in ("OWN", "RENTAL")]
        scenarios.sort(key=lambda scenario: (scenario.probable_cost is None, scenario.probable_cost or _ZERO, scenario.scenario))
        recommended, reason = _choose(scenarios, policy)
        chosen = next((scenario for scenario in scenarios if scenario.scenario == recommended), None)

        warnings = list(chosen.warnings if chosen else ())
        if reason:
            warnings.append(reason)
        if chosen is None:
            union_missing = tuple(sorted({item for scenario in scenarios for item in scenario.missing_inputs}))
            union_assumptions = tuple(sorted({item for scenario in scenarios for item in scenario.assumptions}))
            union_risks = tuple(sorted({item for scenario in scenarios for item in scenario.operational_risks}))
            evidence = tuple(scenarios[0].evidence if scenarios else ())
            return MobilizationAssessment(
                contract_version=CONTRACT_VERSION,
                policy_version=policy.policy_version,
                currency=context.currency.strip().upper(),
                recommended_scenario=recommended,
                alternative_scenarios=tuple(scenarios),
                estimated_cost=None,
                minimum_cost=None,
                probable_cost=None,
                prudent_cost=None,
                cost_per_worker=None,
                cost_per_day=None,
                travel_hours=None,
                non_productive_hours=None,
                productivity_impact="UNKNOWN — no defensible winning scenario",
                operational_risks=union_risks,
                assumptions=union_assumptions,
                missing_inputs=union_missing,
                confidence=0,
                evidence=evidence,
                warnings=tuple(warnings),
            )

        return MobilizationAssessment(
            contract_version=CONTRACT_VERSION,
            policy_version=policy.policy_version,
            currency=context.currency.strip().upper(),
            recommended_scenario=chosen.scenario,
            alternative_scenarios=tuple(scenarios),
            estimated_cost=chosen.probable_cost,
            minimum_cost=chosen.minimum_cost,
            probable_cost=chosen.probable_cost,
            prudent_cost=chosen.prudent_cost,
            cost_per_worker=chosen.cost_per_worker,
            cost_per_day=chosen.cost_per_day,
            travel_hours=chosen.travel_hours,
            non_productive_hours=chosen.non_productive_hours,
            productivity_impact=chosen.productivity_impact,
            operational_risks=chosen.operational_risks,
            assumptions=chosen.assumptions,
            missing_inputs=chosen.missing_inputs,
            confidence=chosen.confidence,
            evidence=chosen.evidence,
            warnings=tuple(warnings),
        )