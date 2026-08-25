from decimal import Decimal

import pytest

from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput


def r(value, quality="QUOTED"):
    return RangeInput.scalar(value, quality=quality, source="money/availability fixture")


def base_context(**overrides):
    values = dict(
        workers=1,
        working_days=1,
        distance_km_one_way=r(1),
        travel_hours_one_way=r(0),
        vehicle_seats=1,
        own_vehicles_available=1,
        rental_available=False,
        currency="EUR",
    )
    values.update(overrides)
    return MobilizationContext(**values)


def base_policy(**overrides):
    values = dict(
        currency="EUR",
        fuel_price_per_litre=r(0),
        own_vehicle_consumption_l_per_100km=r(0),
        own_vehicle_cost_per_km=r(0),
        rental_vehicle_daily_cost=r(0),
        rental_vehicle_consumption_l_per_100km=r(0),
        tolls_per_vehicle_round_trip=r(0),
        parking_per_vehicle_workday=r(0),
        accommodation_per_worker_night=r(10),
        per_diem_per_worker_day=r(0),
        productive_hour_value_per_worker=r(0),
    )
    values.update(overrides)
    return MobilizePolicy(**values)


def by_name(result, name):
    return next(item for item in result.alternative_scenarios if item.scenario == name)


def test_omitted_hotel_availability_is_unknown_not_available():
    result = Mobilize.evaluate(base_context(), base_policy())
    for name in ("accommodation_own", "weekday_hybrid_own"):
        scenario = by_name(result, name)
        assert scenario.availability_state == "UNKNOWN"
        assert scenario.available is False
        assert scenario.comparable is False
        assert "hotel_available" in scenario.missing_inputs
    assert result.recommended_scenario == "daily_commute_own"


def test_explicit_hotel_availability_is_tri_state():
    available = Mobilize.evaluate(base_context(hotel_available="AVAILABLE"), base_policy())
    unavailable = Mobilize.evaluate(base_context(hotel_available="UNAVAILABLE"), base_policy())
    unknown = Mobilize.evaluate(base_context(hotel_available="UNKNOWN"), base_policy())
    assert by_name(available, "accommodation_own").availability_state == "AVAILABLE"
    assert by_name(unavailable, "accommodation_own").availability_state == "UNAVAILABLE"
    assert by_name(unknown, "accommodation_own").availability_state == "UNKNOWN"


def test_decimal_money_preserves_values_beyond_binary_float_integer_boundary():
    rate = Decimal(2) ** 53 + Decimal("0.01")
    result = Mobilize.evaluate(
        base_context(),
        base_policy(own_vehicle_cost_per_km=r(rate)),
    )
    commute = by_name(result, "daily_commute_own")
    assert commute.probable_cost == Decimal("18014398509481984.02")
    assert commute.probable_cost - Decimal("18014398509481984") == Decimal("0.02")


def test_fractional_cent_rates_are_not_binary_float_rounded():
    result = Mobilize.evaluate(
        base_context(),
        base_policy(own_vehicle_cost_per_km=r(Decimal("0.001"))),
    )
    commute = by_name(result, "daily_commute_own")
    assert commute.probable_cost == Decimal("0.002")
    assert result.to_dict()["probable_cost"] == "0.002"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", Decimal("NaN")])
def test_non_finite_money_is_rejected(value):
    with pytest.raises(ValueError, match="finite non-negative"):
        base_policy(own_vehicle_cost_per_km=r(value))


def test_unknown_own_vehicle_availability_does_not_become_assumed_available():
    result = Mobilize.evaluate(base_context(own_vehicles_available=None), base_policy())
    own = by_name(result, "daily_commute_own")
    assert own.availability_state == "UNKNOWN"
    assert own.available is False
    assert own.comparable is False
    assert "own_vehicles_available" in own.missing_inputs
    assert result.recommended_scenario == "NO CLEAR WINNER"


def test_mixed_currency_still_fails_closed_without_fx():
    with pytest.raises(ValueError, match="FX conversion is outside Mobilize V1"):
        Mobilize.evaluate(base_context(currency="EUR"), base_policy(currency="PLN"))
