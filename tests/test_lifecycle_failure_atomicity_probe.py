"""Probe source-side atomicity when lifecycle persistence fails after prior writes."""
import sqlite3

import pytest

import source_runtime
from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor, record_source_result, source_health_contract
from source_metadata import get_source_metadata
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync

SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "ocds-lifecycle-failure:lot:1"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _record(updated_at, actionable, status, title):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "taxonomy": "CPV",
        "category_code": "45200000",
        "source_status": status,
        "source_updated_at": updated_at,
        "is_actionable": actionable,
        "lifecycle_status": status,
        "lifecycle_reason": f"publisher reports {status}",
    }


def _health(conn):
    return source_health_contract(conn, sources=[SOURCE])["items"][0]


def test_lifecycle_failure_rolls_back_signal_metadata_cursor_and_degrades_health(monkeypatch):
    conn = _conn()
    discard_staged_source_syncs()

    baseline = _record("2026-08-28T10:00:00Z", True, "active", "baseline")
    stage_source_sync(SOURCE, [baseline], "cursor-baseline")
    first = commit_staged_source_syncs(conn)
    assert first["signal_records"] == 1
    assert first["metadata_records"] == 1
    assert first["lifecycle_records"] == 1
    assert get_source_cursor(conn, SOURCE) == "cursor-baseline"

    record_source_result(conn, SOURCE, success=True, duration_ms=5, found=1, new_items=1)
    before_health = _health(conn)
    assert before_health["health"] == "healthy"

    def fail_lifecycle(conn_, records, *, commit=True):
        # Signal and metadata persistence have already executed in this transaction.
        raise sqlite3.OperationalError("injected lifecycle persistence failure")

    monkeypatch.setattr(source_runtime, "persist_lifecycle_observations", fail_lifecycle)

    newer = _record("2026-08-28T11:00:00Z", False, "cancelled", "must rollback")
    stage_source_sync(SOURCE, [newer], "cursor-must-not-commit")
    with pytest.raises(sqlite3.OperationalError, match="injected lifecycle persistence failure"):
        commit_staged_source_syncs(conn)

    signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
    metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
    lifecycle = lifecycle_for(conn, SOURCE, EXTERNAL_ID)

    assert signal["title"] == "baseline"
    assert signal["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert metadata["source_status"] == "active"
    assert metadata["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert lifecycle["is_actionable"] == 1
    assert lifecycle["lifecycle_status"] == "active"
    assert get_source_cursor(conn, SOURCE) == "cursor-baseline"

    after_health = _health(conn)
    assert after_health["health"] == "degraded"
    assert after_health["consecutive_failures"] == 1
    assert str(after_health["last_error"]).startswith("ingestion_commit_failed:OperationalError")
    assert after_health["last_success"] == before_health["last_success"]

    assert commit_staged_source_syncs(conn) == {
        "sources": 0,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 0,
    }
