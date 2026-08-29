import pytest

from factory_cloud.portfolio_priority import PortfolioPriorityError, priority_for_app


def _app(**signals):
    return {"activation": {"priority": 50}, "portfolio_priority": signals}


def test_safety_dominates_commercial_polish():
    safety = priority_for_app(_app(safety_severity=1, commercial_leverage=0))
    commercial = priority_for_app(_app(safety_severity=0, commercial_leverage=100, shared_leverage=100))
    assert safety.score > commercial.score


def test_pilot_blocker_dominates_shared_leverage():
    pilot = priority_for_app(_app(pilot_blocker=10))
    shared = priority_for_app(_app(shared_leverage=100))
    assert pilot.score > shared.score


def test_invalid_signal_fails_closed():
    with pytest.raises(PortfolioPriorityError):
        priority_for_app(_app(safety_severity=101))
