import json
import math

import pytest

from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput


def r(value, quality="QUOTED"):
    return RangeInput.scalar(value, quality=quality, source="hardening fixture")


def context(**overrides):
    data = dict(
        workers=5,
        working_days=20,
        distance_km_one_way=r(50),
        travel_hours_one_way=r(0.6),
        vehicle_seats=5,
        own_vehicles_available=1,
        currency="EUR",
    )
    data.update(overrides)
    return MobilizationContext(**data)


def policy(**overrides):
    data = dict(
        currency="EUR",
        fuel_price_per_litre=r(1.8),
        own_vehicle_consumption_l_per_100km=r(8),
        own_vehicle_cost_per_km=r(0.10),
        rental_vehicle_daily_cost=r(70),
        rental_vehicle_consumption_l_per_100km=r(8),
        tolls_per_vehicle_round_trip=r(0),
        parking_per_vehicle_workday=r(0),
        accommodation_per_worker_night=r(60),
        per_diem_per_worker_day=r(0),
        productive_hour_value_per_worker=r(0),
    )
    data.update(overrides)
    return MobilizePolicy(**data)


def by_name(result, name):
    return next(s for s in result.alternative_scenarios if s.scenario == name)


def test_invalid_evidence_quality_is_rejected_at_contract_boundary():
    invalid = RangeInput.scalar(50, quality="BOGUS", source="bad input")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported evidence quality"):
        Mobilize.evaluate(context(distance_km_one_way=invalid), policy())


def test_non_finite_range_values_are_rejected():
    for value in (math.inf, math.nan):
        with pytest.raises(ValueError, match="finite non-negative"):
            Mobilize.evaluate(context(distance_km_one_way=r(value)), policy())


def test_unknown_fuel_price_blocks_non_zero_distance_comparison():
    result = Mobilize.evaluate(context(), policy(fuel_price_per_litre=RangeInput()))
    assert all(not s.comparable for s in result.alternative_scenarios)
    assert result.recommended_scenario == "NO CLEAR WINNER"


def test_unknown_consumption_blocks_only_affected_vehicle_mode():
    result = Mobilize.evaluate(
        context(),
        policy(own_vehicle_consumption_l_per_100km=RangeInput()),
    )
    assert not by_name(result, "daily_commute_own").comparable
    assert by_name(result, "daily_commute_rental").comparable


def test_unknown_own_vehicle_cost_blocks_own_mode_at_non_zero_distance():
    result = Mobilize.evaluate(context(), policy(own_vehicle_cost_per_km=RangeInput()))
    assert not by_name(result, "daily_commute_own").comparable
    assert by_name(result, "daily_commute_rental").comparable


def test_zero_distance_does_not_require_fuel_or_own_km_cost_to_compare():
    result = Mobilize.evaluate(
        context(distance_km_one_way=r(0), travel_hours_one_way=r(0)),
        policy(
            fuel_price_per_litre=RangeInput(),
            own_vehicle_consumption_l_per_100km=RangeInput(),
            own_vehicle_cost_per_km=RangeInput(),
        ),
    )
    assert by_name(result, "daily_commute_own").comparable


def test_policy_rejects_invalid_near_cost_thresholds():
    with pytest.raises(ValueError, match="near_cost_ratio"):
        Mobilize.evaluate(context(), policy(near_cost_ratio=0.99))
    with pytest.raises(ValueError, match="material_travel_reduction_hours"):
        Mobilize.evaluate(context(), policy(material_travel_reduction_hours=-0.1))


def test_assessment_contract_is_json_safe_and_complete():
    payload = Mobilize.evaluate(context(), policy()).to_dict()

    encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded["contract_version"] == "mobilize.v1"
    assert decoded["policy_version"] == "mobilize-policy-v1"
    scenarios = decoded["alternative_scenarios"]
    assert len(scenarios) == 6
    assert len({scenario["scenario"] for scenario in scenarios}) == 6
