from math import isfinite

from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput


def r(value):
    return RangeInput.scalar(value, quality="QUOTED", source="edge fixture")


def complete_policy(**overrides):
    values = dict(
        currency="EUR",
        fuel_price_per_litre=r(0),
        own_vehicle_consumption_l_per_100km=r(0),
        own_vehicle_cost_per_km=r(0),
        rental_vehicle_daily_cost=r(0),
        rental_vehicle_consumption_l_per_100km=r(0),
        tolls_per_vehicle_round_trip=r(0),
        parking_per_vehicle_workday=r(0),
        accommodation_per_worker_night=r(0),
        per_diem_per_worker_day=r(0),
        productive_hour_value_per_worker=r(0),
    )
    values.update(overrides)
    return MobilizePolicy(**values)


def test_equal_cost_scenarios_return_no_clear_winner():
    result = Mobilize.evaluate(
        MobilizationContext(
            workers=5,
            working_days=10,
            distance_km_one_way=r(0),
            travel_hours_one_way=r(0),
            own_vehicles_available=1,
            currency="EUR",
        ),
        complete_policy(),
    )
    assert result.recommended_scenario == "NO CLEAR WINNER"
    assert result.estimated_cost is None
    assert any("ranges overlap" in warning for warning in result.warnings)


def test_very_long_duration_remains_finite_and_deterministic():
    context = MobilizationContext(
        workers=50,
        working_days=10_000,
        distance_km_one_way=r(120),
        travel_hours_one_way=r(1.5),
        own_vehicles_available=10,
        currency="EUR",
    )
    policy = complete_policy(
        fuel_price_per_litre=r(1.8),
        own_vehicle_consumption_l_per_100km=r(8),
        own_vehicle_cost_per_km=r(0.15),
        accommodation_per_worker_night=r(40),
        rental_vehicle_daily_cost=r(60),
    )
    first = Mobilize.evaluate(context, policy)
    second = Mobilize.evaluate(context, policy)
    assert first.to_dict() == second.to_dict()
    for scenario in first.alternative_scenarios:
        if scenario.probable_cost is not None:
            assert isfinite(scenario.probable_cost)
            assert scenario.probable_cost >= 0


def test_more_days_never_reduce_daily_commute_absolute_cost():
    policy = complete_policy(
        fuel_price_per_litre=r(1.8),
        own_vehicle_consumption_l_per_100km=r(8),
        own_vehicle_cost_per_km=r(0.15),
    )

    def commute(days):
        result = Mobilize.evaluate(
            MobilizationContext(
                workers=10,
                working_days=days,
                distance_km_one_way=r(100),
                travel_hours_one_way=r(1),
                own_vehicles_available=2,
                currency="EUR",
            ),
            policy,
        )
        return next(
            scenario
            for scenario in result.alternative_scenarios
            if scenario.scenario == "daily_commute_own"
        ).probable_cost

    assert commute(100) > commute(10) > commute(1)
