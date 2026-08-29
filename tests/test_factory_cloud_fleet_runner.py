from datetime import datetime, timezone

import pytest

from factory_cloud.fleet_runner import FleetRunnerError, build_dispatch, select_next_factory


def _switchboard():
    return {
        "scope": "switchboard_only",
        "default_signal": "X",
        "factories": [
            {"id": "alpha", "name": "Alpha", "target": "Alpha"},
            {"id": "factory-cloud", "name": "Factory Cloud", "target": "Control", "signal": "D"},
            {"id": "gamma", "name": "Gamma", "target": "Gamma"},
        ],
    }


def _state(**overrides):
    state = {
        "command": "D",
        "status": "ACTIVE",
        "cursor": 0,
        "last_factory_id": None,
        "last_run_at": None,
        "last_material_change": None,
        "blocked": [],
    }
    state.update(overrides)
    return state


def test_select_next_factory_rotates_from_cursor():
    factory, index = select_next_factory(_switchboard(), _state(cursor=1))
    assert factory["id"] == "factory-cloud"
    assert index == 1


def test_select_next_factory_skips_blocked_and_wraps():
    factory, index = select_next_factory(
        _switchboard(),
        _state(cursor=2, blocked=[{"factory_id": "gamma"}, "alpha"]),
    )
    assert factory["id"] == "factory-cloud"
    assert index == 1


def test_select_next_factory_fails_closed_when_all_are_blocked():
    with pytest.raises(FleetRunnerError, match="all registered factories are blocked"):
        select_next_factory(_switchboard(), _state(blocked=["alpha", "factory-cloud", "gamma"]))


def test_build_dispatch_advances_cursor_without_claiming_execution():
    instant = datetime(2026, 8, 29, 15, 35, tzinfo=timezone.utc)
    packet, updated = build_dispatch(_switchboard(), _state(cursor=0), now=instant)

    assert packet["factory_id"] == "alpha"
    assert packet["signal"] == "X"
    assert updated["cursor"] == 1
    assert updated["last_factory_id"] == "alpha"
    assert updated["last_run_at"] == "2026-08-29T15:35:00Z"
    assert updated["last_material_change"] == {
        "kind": "DISPATCH_SELECTED_NO_EXECUTION_CLAIM",
        "factory_id": "alpha",
        "evidence": "registry+fleet_state",
    }
