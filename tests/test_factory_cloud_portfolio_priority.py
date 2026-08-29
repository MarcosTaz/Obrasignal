import pytest

from factory_cloud.portfolio_priority import PortfolioPriorityError, priority_for_app


def _app(**signals):
    return {"activation": {"priority": 50}, "portfolio_priority": signals}


def test_safety_dominates_everything_below_it():
    safety = priority_for_app(_app(safety_severity=1))
    lower = priority_for_app(_app(pilot_safe_blocker=100, shared_leverage=100, evidence_integrity=100, pilot_blocker=100, commercial_leverage=100))
    assert safety.score > lower.score


def test_pilot_safe_blocker_dominates_commercial_exposure():
    pilot_safe = priority_for_app(_app(pilot_safe_blocker=1))
    commercial = priority_for_app(_app(commercial_leverage=100, pilot_blocker=100))
    assert pilot_safe.score > commercial.score


def test_shared_unblock_dominates_single_factory_commercial_leverage():
    shared = priority_for_app(_app(shared_leverage=1))
    commercial = priority_for_app(_app(commercial_leverage=100, pilot_blocker=100))
    assert shared.score > commercial.score


def test_evidence_integrity_dominates_legacy_pilot_and_commercial_signals():
    integrity = priority_for_app(_app(evidence_integrity=1))
    lower = priority_for_app(_app(pilot_blocker=100, commercial_leverage=100))
    assert integrity.score > lower.score


def test_invalid_signal_fails_closed():
    with pytest.raises(PortfolioPriorityError):
        priority_for_app(_app(pilot_safe_blocker=101))
