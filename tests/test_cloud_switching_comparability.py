from decimal import Decimal

from cloud_switching.comparability import ComparabilityGrade, ObservationWindow, assess_comparability

D = Decimal


def test_same_window_and_workload_units_can_be_grade_a():
    result = assess_comparability(
        pre_cost=D("120000"),
        post_cost=D("90000"),
        pre=ObservationWindow(12, D("1200000"), "gold"),
        post=ObservationWindow(12, D("1500000"), "gold"),
    )
    assert result.grade is ComparabilityGrade.A
    assert result.comparable
    assert result.normalized_pre_cost_per_unit == D("0.1")
    assert result.normalized_post_cost_per_unit == D("0.06")


def test_missing_denominator_on_one_side_is_unverified_comparability():
    result = assess_comparability(
        pre_cost=D("120000"),
        post_cost=D("90000"),
        pre=ObservationWindow(12, D("1200000"), "gold"),
        post=ObservationWindow(12, None, "gold"),
    )
    assert result.grade is ComparabilityGrade.U
    assert not result.comparable


def test_changed_service_level_is_not_treated_as_strongly_comparable():
    result = assess_comparability(
        pre_cost=D("120000"),
        post_cost=D("90000"),
        pre=ObservationWindow(12, D("1200000"), "gold"),
        post=ObservationWindow(12, D("1200000"), "bronze"),
    )
    assert result.grade is ComparabilityGrade.C
    assert not result.comparable


def test_same_window_without_volume_normalization_is_directional_grade_b():
    result = assess_comparability(
        pre_cost=D("120000"),
        post_cost=D("90000"),
        pre=ObservationWindow(12),
        post=ObservationWindow(12),
    )
    assert result.grade is ComparabilityGrade.B
    assert result.comparable
