from decimal import Decimal, getcontext

import pytest

from factories.capacity_commitment.engine import CommitmentState
from factories.capacity_commitment.time_bucket import (
    CommitmentBucket,
    ExceptionSeverity,
    reconcile_time_buckets,
)


def bucket(period, state, committed, actual, *, forecast=None, units="0", percent="0", refs=()):
    return CommitmentBucket(
        period_id=period,
        commitment_state=state,
        committed_units=Decimal(committed),
        actual_units=Decimal(actual),
        forecast_units=None if forecast is None else Decimal(forecast),
        alert_tolerance_units=Decimal(units),
        alert_tolerance_percent=Decimal(percent),
        source_refs=refs,
    )


def test_firm_buckets_reconcile_exact_shortfall_and_rank_exceptions():
    result = reconcile_time_buckets(
        [
            bucket("2026-01", CommitmentState.FIRM, "10000", "6000", forecast="11000", percent="5", refs=("contract:1",)),
            bucket("2026-02", CommitmentState.FLEX_WINDOW, "10000", "9200", forecast="9800", units="1000", refs=("amendment:2",)),
        ]
    )
    assert result.firm_committed_units == Decimal("20000")
    assert result.actual_units_for_firm_periods == Decimal("15200")
    assert result.firm_shortfall_units == Decimal("4800")
    assert result.exception_periods == ("2026-01",)
    jan, feb = result.buckets
    assert jan.firm_shortfall_units == Decimal("4000")
    assert jan.alert_threshold_units == Decimal("500")
    assert jan.severity is ExceptionSeverity.CRITICAL
    assert feb.firm_shortfall_units == Decimal("800")
    assert feb.outside_alert_tolerance is False
    assert feb.severity is ExceptionSeverity.NONE


def test_forecast_only_never_becomes_firm_shortfall_or_exception():
    result = reconcile_time_buckets(
        [bucket("2026-03", CommitmentState.FORECAST_ONLY, "0", "5000", forecast="12000", refs=("forecast:3",))]
    )
    item = result.buckets[0]
    assert item.firm_shortfall_units == Decimal("0")
    assert item.outside_alert_tolerance is False
    assert result.firm_committed_units == Decimal("0")
    assert result.firm_shortfall_units == Decimal("0")
    assert result.forecast_units == Decimal("12000")
    assert result.forecast_variance_units == Decimal("7000")


def test_nonfirm_bucket_rejects_fake_committed_volume():
    with pytest.raises(ValueError, match="non-firm bucket"):
        reconcile_time_buckets([bucket("2026-03", CommitmentState.FORECAST_ONLY, "10000", "5000", forecast="10000")])


def test_alert_tolerance_never_changes_contractual_shortfall():
    result = reconcile_time_buckets(
        [bucket("2026-04", CommitmentState.FIRM, "10000", "9500", units="1000", percent="20")]
    )
    item = result.buckets[0]
    assert item.alert_threshold_units == Decimal("2000")
    assert item.outside_alert_tolerance is False
    assert item.firm_shortfall_units == Decimal("500")
    assert result.firm_shortfall_units == Decimal("500")


def test_duplicate_period_is_rejected_instead_of_double_counted():
    with pytest.raises(ValueError, match="duplicate period_id"):
        reconcile_time_buckets(
            [
                bucket("2026Q1", CommitmentState.FIRM, "100", "50"),
                bucket("2026Q1", CommitmentState.FIRM, "100", "50"),
            ]
        )


def test_time_bucket_math_ignores_hostile_global_decimal_precision():
    old = getcontext().prec
    try:
        getcontext().prec = 4
        result = reconcile_time_buckets(
            [bucket("2026Q2", CommitmentState.FIRM, "12345678901234567890.25", "0.25", percent="0.01")]
        )
    finally:
        getcontext().prec = old
    assert result.firm_shortfall_units == Decimal("12345678901234567890.00")
    assert result.buckets[0].alert_threshold_units == Decimal("1234567890123456.789025")


def test_invalid_precision_inputs_and_tolerance_fail_closed():
    with pytest.raises(ValueError, match="exact Decimal"):
        reconcile_time_buckets(
            [
                CommitmentBucket(
                    period_id="2026Q3",
                    commitment_state=CommitmentState.FIRM,
                    committed_units=100,  # type: ignore[arg-type]
                    actual_units=Decimal("50"),
                )
            ]
        )
    with pytest.raises(ValueError, match="cannot exceed 100"):
        reconcile_time_buckets([bucket("2026Q3", CommitmentState.FIRM, "100", "50", percent="101")])
