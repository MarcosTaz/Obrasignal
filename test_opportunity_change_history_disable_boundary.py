import sqlite3
from types import SimpleNamespace

import pytest

import source_runtime as runtime
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _record():
    return {
        "source": "DISABLED_HISTORY_SOURCE",
        "signal_type": "TENDER",
        "external_id": "DISABLED-1",
        "title": "Still persist Signal",
        "deadline": "2026-10-01T12:00:00Z",
        "source_status": "Open",
        "is_actionable": True,
        "lifecycle_status": "open",
    }


@pytest.mark.parametrize("state", ["RESEARCH", "EXPERIMENT", "DISABLED"])
def test_non_promoted_capability_skips_history_without_blocking_source_commit(monkeypatch, state):
    conn = _conn()
    runtime.discard_staged_source_syncs()
    monkeypatch.setattr(runtime, "capability", lambda name: SimpleNamespace(state=state))

    def history_must_not_run(*args, **kwargs):
        raise AssertionError(f"history persistence ran while capability was {state}")

    monkeypatch.setattr(runtime, "persist_change_observations", history_must_not_run)
    runtime.stage_source_sync("DISABLED_HISTORY_SOURCE", [_record()], f"cursor-{state.lower()}")

    result = runtime.commit_staged_source_syncs(conn)

    assert result["signal_records"] == 1
    assert get_signal_record(conn, "DISABLED_HISTORY_SOURCE", "DISABLED-1") is not None
    assert get_source_cursor(conn, "DISABLED_HISTORY_SOURCE") == f"cursor-{state.lower()}"
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_snapshots'"
    ).fetchone() is None
