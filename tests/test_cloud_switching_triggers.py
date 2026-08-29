from datetime import date

import pytest

from cloud_switching.triggers import TriggerTimingClass, TriggerWindow


def test_market_dialogue_detected_early_preserves_forecast_freeze_window():
    window = TriggerWindow(
        published_on=date(2026, 8, 22),
        detected_on=date(2026, 8, 23),
        decision_deadline=date(2026, 10, 31),
    )
    assert window.detection_latency_days == 1
    assert window.days_remaining_at_detection == 69
    assert window.timing_class is TriggerTimingClass.EARLY_DIALOGUE
    assert window.forecast_freeze_window_viable is True


def test_open_tender_with_weeks_remaining_is_actionable():
    window = TriggerWindow(
        published_on=date(2026, 8, 24),
        detected_on=date(2026, 8, 29),
        decision_deadline=date(2026, 9, 24),
    )
    assert window.detection_latency_days == 5
    assert window.days_remaining_at_detection == 26
    assert window.timing_class is TriggerTimingClass.ACTIONABLE
    assert window.forecast_freeze_window_viable is True


def test_late_detection_is_not_silently_called_actionable():
    window = TriggerWindow(
        published_on=date(2026, 8, 19),
        detected_on=date(2026, 8, 25),
        decision_deadline=date(2026, 8, 26),
    )
    assert window.timing_class is TriggerTimingClass.TOO_LATE
    assert window.forecast_freeze_window_viable is False


def test_closed_trigger_is_not_viable():
    window = TriggerWindow(
        published_on=date(2026, 7, 27),
        detected_on=date(2026, 8, 29),
        decision_deadline=date(2026, 8, 27),
    )
    assert window.timing_class is TriggerTimingClass.CLOSED
    assert window.forecast_freeze_window_viable is False


def test_impossible_dates_fail_closed():
    with pytest.raises(ValueError, match="cannot precede publication"):
        TriggerWindow(
            published_on=date(2026, 8, 29),
            detected_on=date(2026, 8, 28),
            decision_deadline=date(2026, 9, 10),
        ).detection_latency_days
