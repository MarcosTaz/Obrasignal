from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from bangs.accommodation import AccommodationCandidate, AccommodationType, RateBasis, assess_accommodation
from bangs.evidence import ConfirmationState, EvidenceBasis, SourceEvidence
from bangs.money import Money
from bangs.routes import (
    DistanceBasis, FuelObservation, RouteDirection, RouteFacts, TravelCharge,
    TravelChargeKind, VehicleEconomics, assess_route_cost,
)

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
EV = SourceEvidence("route-provider", EvidenceBasis.PROVIDER_FACT, NOW)
FUEL_EV = SourceEvidence("fuel-source", EvidenceBasis.MARKET_OBSERVATION, NOW)

def vehicle(consumption="10"):
    return VehicleEconomics(Decimal(consumption), FuelObservation(Money.of("1.80", "EUR"), "PT", FUEL_EV))

def test_route_one_way_fuel_math():
    r = assess_route_cost(RouteFacts(Decimal("300"), Decimal("180"), DistanceBasis.ROAD_PROVIDER, EV), vehicle(), direction=RouteDirection.ONE_WAY, tolls_known=True)
    assert r.distance_km_total == 300
    assert r.fuel_litres == 30
    assert r.assessment.known_total.amount == Decimal("54.00")

def test_round_trip_multiple_trips_and_tolls_per_leg():
    r = assess_route_cost(
        RouteFacts(Decimal("100"), Decimal("60"), DistanceBasis.ROAD_PROVIDER, EV), vehicle("8"),
        direction=RouteDirection.ROUND_TRIP, number_of_trips=3,
        charges=(TravelCharge(TravelChargeKind.TOLL, Money.of(5, "EUR"), EV, per_leg=True),),
        tolls_known=True,
    )
    assert r.distance_km_total == 600
    assert r.fuel_litres == 48
    assert r.assessment.known_total.amount == Decimal("116.40")  # fuel 86.4 + toll 30

def test_unknown_toll_is_unknown_not_zero():
    r = assess_route_cost(RouteFacts(100, 60, DistanceBasis.ROAD_PROVIDER, EV), vehicle(), direction=RouteDirection.ONE_WAY, tolls_known=False)
    assert "tolls" in r.assessment.unknown_components

def test_zero_distance_is_valid_and_zero_fuel_cost():
    r = assess_route_cost(RouteFacts(0, 0, DistanceBasis.ROAD_PROVIDER, EV), vehicle(), direction=RouteDirection.ONE_WAY, tolls_known=True)
    assert r.fuel_litres == 0
    assert r.assessment.known_total.amount == 0

def test_ferry_component_supported_without_booking_platform():
    r = assess_route_cost(RouteFacts(20, 30, DistanceBasis.ROAD_PROVIDER, EV), vehicle(), direction=RouteDirection.ONE_WAY, charges=(TravelCharge(TravelChargeKind.FERRY, Money.of(40, "EUR"), EV),), tolls_known=True)
    assert any(x.code == "travel_ferry" for x in r.assessment.lines)

def test_paid_travel_time_requires_explicit_rate_crew_and_time():
    r = assess_route_cost(RouteFacts(100, None, DistanceBasis.ROAD_PROVIDER, EV), vehicle(), direction=RouteDirection.ONE_WAY, travel_time_paid=True, tolls_known=True)
    assert "paid_travel_time" in r.assessment.unknown_components
    r2 = assess_route_cost(RouteFacts(100, 120, DistanceBasis.ROAD_PROVIDER, EV), vehicle(), direction=RouteDirection.ONE_WAY, travel_time_paid=True, paid_travel_time_rate_per_hour=Money.of(20, "EUR"), crew_size=10, tolls_known=True)
    assert any(x.code == "paid_travel_time" and x.amount.amount == 400 for x in r2.assessment.lines)

def test_straight_line_distance_never_masquerades_as_road_distance():
    r = assess_route_cost(RouteFacts(100, None, DistanceBasis.STRAIGHT_LINE), vehicle(), direction=RouteDirection.ONE_WAY, tolls_known=True)
    assert "STRAIGHT_LINE_DISTANCE_NOT_ROAD_DISTANCE" in r.assessment.warnings

def test_invalid_consumption_rejected():
    with pytest.raises(ValueError): vehicle("101")

def hotel(rate=70, basis=RateBasis.ROOM_PER_NIGHT, cap=2, confirmation=ConfirmationState.AVAILABILITY_CONFIRMED, valid_until=None):
    evidence = SourceEvidence("hotel-source", EvidenceBasis.LIVE_LIST_PRICE, NOW, valid_until=valid_until)
    return AccommodationCandidate("h", "Hotel A", AccommodationType.HOTEL, Money.of(rate, "EUR"), basis, cap, evidence, confirmation)

def test_room_rate_uses_rooms_not_people():
    a = assess_accommodation(hotel(), crew_size=8, nights=30, now=NOW)
    assert a.rate_units_required == 4
    assert a.assessment.known_total.amount == Decimal("8400")

def test_odd_crew_rounds_room_count_up():
    a = assess_accommodation(hotel(), crew_size=9, nights=1, now=NOW)
    assert a.rate_units_required == 5
    assert a.assessment.known_total.amount == 350

def test_person_rate_is_not_room_rate():
    a = assess_accommodation(hotel(rate=30, basis=RateBasis.PERSON_PER_NIGHT, cap=None), crew_size=8, nights=2, now=NOW)
    assert a.rate_units_required == 8
    assert a.assessment.known_total.amount == 480

def test_apartment_rate_capacity():
    c = AccommodationCandidate("a", "Apartment", AccommodationType.APARTMENT, Money.of(140, "EUR"), RateBasis.APARTMENT_PER_NIGHT, 4, SourceEvidence("apts", EvidenceBasis.MARKET_OBSERVATION, NOW), ConfirmationState.AVAILABILITY_UNKNOWN)
    a = assess_accommodation(c, crew_size=8, nights=30, now=NOW)
    assert a.rate_units_required == 2
    assert a.assessment.known_total.amount == 8400
    assert "AVAILABILITY_UNKNOWN" in a.assessment.warnings

def test_weekly_and_monthly_rates_have_explicit_period_rounding():
    c = AccommodationCandidate("w", "Long stay", AccommodationType.LONG_STAY, Money.of(700, "EUR"), RateBasis.WEEKLY, 4, SourceEvidence("long", EvidenceBasis.SUPPLIER_QUOTE, NOW), ConfirmationState.AVAILABILITY_CONFIRMED)
    a = assess_accommodation(c, crew_size=8, nights=8, now=NOW)
    assert a.billing_periods == 2
    assert a.assessment.known_total.amount == 2800

def test_expired_rate_remains_observation_but_not_current_cost():
    c = hotel(valid_until=NOW + timedelta(days=1))
    a = assess_accommodation(c, crew_size=2, nights=2, now=NOW + timedelta(days=2))
    assert "RATE_EXPIRED" in a.assessment.warnings
    assert "current_accommodation_rate" in a.assessment.unknown_components

def test_unknown_rate_basis_blocks_fake_cost():
    c = hotel(basis=RateBasis.UNKNOWN, cap=None)
    a = assess_accommodation(c, crew_size=8, nights=10, now=NOW)
    assert a.assessment.known_total is None
    assert "rate_basis" in a.assessment.unknown_components
