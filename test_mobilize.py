import pytest

from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput


def r(value, quality="QUOTED"):
    return RangeInput.scalar(value, quality=quality, source="test fixture")


def rr(a, b, c, quality="ESTIMATED"):
    return RangeInput(a, b, c, quality=quality, source="test fixture")


def context(**overrides):
    data = dict(
        workers=5,
        working_days=20,
        distance_km_one_way=r(50),
        travel_hours_one_way=r(0.6),
        vehicle_seats=5,
        own_vehicles_available=1,
        hotel_available=True,
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
        maximum_daily_travel_hours=3,
        fatigue_risk_travel_hours=2,
    )
    data.update(overrides)
    return MobilizePolicy(**data)


def by_name(result, name):
    return next(s for s in result.alternative_scenarios if s.scenario == name)


def test_daily_commute_cheaper():
    result = Mobilize.evaluate(
        context(distance_km_one_way=r(5)),
        policy(accommodation_per_worker_night=r(100)),
    )
    assert result.recommended_scenario == "daily_commute_own"


def test_accommodation_cheaper_for_long_expensive_commute():
    result = Mobilize.evaluate(
        context(working_days=60, distance_km_one_way=r(250), travel_hours_one_way=r(3)),
        policy(accommodation_per_worker_night=r(10), productive_hour_value_per_worker=r(40)),
    )
    assert result.recommended_scenario in {"accommodation_own", "weekday_hybrid_own"}
    assert by_name(result, "daily_commute_own").probable_cost > result.probable_cost


def test_weekday_hybrid_can_be_cheapest():
    result = Mobilize.evaluate(
        context(working_days=20, distance_km_one_way=r(140), travel_hours_one_way=r(1.5)),
        policy(accommodation_per_worker_night=r(25), productive_hour_value_per_worker=r(10)),
    )
    assert result.recommended_scenario == "weekday_hybrid_own"


def test_own_vehicle_vs_rental():
    own = Mobilize.evaluate(context(), policy(rental_vehicle_daily_cost=r(300)))
    assert by_name(own, "daily_commute_own").probable_cost < by_name(
        own, "daily_commute_rental"
    ).probable_cost
    rental = Mobilize.evaluate(
        context(),
        policy(own_vehicle_cost_per_km=r(2), rental_vehicle_daily_cost=r(10)),
    )
    assert by_name(rental, "daily_commute_rental").probable_cost < by_name(
        rental, "daily_commute_own"
    ).probable_cost


def test_zero_distance_removes_distance_fuel_and_wear_cost():
    result = Mobilize.evaluate(
        context(distance_km_one_way=r(0), travel_hours_one_way=r(0)),
        policy(),
    )
    commute = by_name(result, "daily_commute_own")
    assert commute.metrics["total_vehicle_km"]["probable"] == 0
    assert commute.direct_cost.probable == 0


def test_single_worker_supported():
    result = Mobilize.evaluate(context(workers=1), policy())
    assert result.cost_per_worker == result.probable_cost


def test_large_crew_scales_vehicle_requirement():
    result = Mobilize.evaluate(context(workers=101, own_vehicles_available=30), policy())
    assert by_name(result, "daily_commute_own").metrics["vehicles_required"] == 21


def test_short_and_long_duration_monotonic_for_same_scenario():
    short = Mobilize.evaluate(context(working_days=5), policy())
    long = Mobilize.evaluate(context(working_days=25), policy())
    assert by_name(long, "daily_commute_own").probable_cost > by_name(
        short, "daily_commute_own"
    ).probable_cost


def test_more_workers_do_not_reduce_absolute_accommodation_cost():
    small = Mobilize.evaluate(context(workers=2, own_vehicles_available=5), policy())
    large = Mobilize.evaluate(context(workers=10, own_vehicles_available=5), policy())
    assert by_name(large, "weekday_hybrid_own").probable_cost > by_name(
        small, "weekday_hybrid_own"
    ).probable_cost


def test_missing_optional_cost_is_visible_not_silently_known():
    result = Mobilize.evaluate(
        context(),
        policy(parking_per_vehicle_workday=RangeInput()),
    )
    commute = by_name(result, "daily_commute_own")
    assert "parking_per_vehicle_workday" in commute.missing_inputs
    assert commute.comparable
    assert commute.confidence < 100
    assert any("excludes unknown components" in warning for warning in commute.warnings)


def test_missing_hotel_cost_makes_stay_scenarios_non_comparable():
    result = Mobilize.evaluate(
        context(),
        policy(accommodation_per_worker_night=RangeInput()),
    )
    assert not by_name(result, "accommodation_own").comparable
    assert not by_name(result, "weekday_hybrid_own").comparable
    assert "accommodation_per_worker_night" in by_name(
        result, "weekday_hybrid_own"
    ).missing_inputs


@pytest.mark.parametrize(
    "field,value",
    [("workers", 0), ("workers", -1), ("working_days", 0), ("working_days", -1)],
)
def test_invalid_non_positive_core_inputs(field, value):
    with pytest.raises(ValueError):
        Mobilize.evaluate(context(**{field: value}), policy())


def test_negative_range_input_rejected():
    with pytest.raises(ValueError):
        Mobilize.evaluate(context(distance_km_one_way=r(-1)), policy())


def test_partial_range_rejected_to_prevent_false_precision():
    with pytest.raises(ValueError):
        Mobilize.evaluate(
            context(
                distance_km_one_way=RangeInput(
                    10,
                    12,
                    None,
                    quality="ESTIMATED",
                )
            ),
            policy(),
        )


def test_unknown_distance_returns_no_clear_winner():
    result = Mobilize.evaluate(context(distance_km_one_way=RangeInput()), policy())
    assert result.recommended_scenario == "NO CLEAR WINNER"
    assert result.estimated_cost is None
    assert result.confidence == 0


def test_deterministic_output():
    one = Mobilize.evaluate(context(), policy()).to_dict()
    two = Mobilize.evaluate(context(), policy()).to_dict()
    assert one == two


def test_confidence_degrades_with_estimates_and_missing_inputs():
    strong = Mobilize.evaluate(
        context(distance_km_one_way=r(50, "LIVE")),
        policy(),
    )
    weak = Mobilize.evaluate(
        context(
            distance_km_one_way=rr(45, 50, 60),
            travel_hours_one_way=RangeInput(),
        ),
        policy(parking_per_vehicle_workday=RangeInput()),
    )
    assert weak.confidence < strong.confidence


def test_uncertainty_range_preserved():
    result = Mobilize.evaluate(
        context(distance_km_one_way=rr(40, 50, 65)),
        policy(fuel_price_per_litre=rr(1.5, 1.8, 2.2)),
    )
    commute = by_name(result, "daily_commute_own")
    assert commute.minimum_cost < commute.probable_cost < commute.prudent_cost


def test_scenario_ranking_stable_for_identical_inputs():
    rankings = []
    for _ in range(5):
        result = Mobilize.evaluate(context(), policy())
        rankings.append([scenario.scenario for scenario in result.alternative_scenarios])
    assert all(item == rankings[0] for item in rankings)


def test_unavailable_modes_are_not_recommended():
    result = Mobilize.evaluate(
        context(own_vehicles_available=0, rental_available=False),
        policy(),
    )
    assert result.recommended_scenario == "NO CLEAR WINNER"
    assert all(not scenario.available for scenario in result.alternative_scenarios)


def test_hotel_unavailable_disables_stay_scenarios():
    result = Mobilize.evaluate(context(hotel_available=False), policy())
    assert not by_name(result, "accommodation_own").available
    assert not by_name(result, "weekday_hybrid_own").available


def test_currency_mismatch_and_missing_currency_rejected():
    with pytest.raises(ValueError):
        Mobilize.evaluate(context(currency="EUR"), policy(currency="USD"))
    with pytest.raises(ValueError):
        Mobilize.evaluate(context(currency=""), policy(currency=""))


def test_equal_or_overlapping_ranges_can_return_no_clear_winner():
    result = Mobilize.evaluate(
        context(
            distance_km_one_way=rr(40, 50, 60),
            travel_hours_one_way=RangeInput(),
        ),
        policy(
            own_vehicle_cost_per_km=rr(0.05, 0.1, 0.2),
            rental_vehicle_daily_cost=rr(5, 20, 80),
            productive_hour_value_per_worker=RangeInput(),
        ),
    )
    allowed = {scenario.scenario for scenario in result.alternative_scenarios}
    allowed.add("NO CLEAR WINNER")
    assert result.recommended_scenario in allowed


def test_fatigue_risk_is_policy_driven_not_hardcoded():
    result = Mobilize.evaluate(
        context(travel_hours_one_way=r(1.2)),
        policy(fatigue_risk_travel_hours=2.0),
    )
    assert "daily travel reaches configured fatigue-risk threshold" in by_name(
        result, "daily_commute_own"
    ).operational_risks


def test_missing_rental_price_does_not_crash_and_blocks_rental_comparison():
    result = Mobilize.evaluate(
        context(),
        policy(rental_vehicle_daily_cost=RangeInput()),
    )
    assert not by_name(result, "daily_commute_rental").comparable


def test_explicit_default_local_transport_is_labelled_assumed():
    result = Mobilize.evaluate(context(), policy())
    commute = by_name(result, "daily_commute_own")
    evidence = {item["input"]: item for item in commute.evidence}
    assert evidence["local_transport_km_per_workday"]["state"] == "ASSUMED"
