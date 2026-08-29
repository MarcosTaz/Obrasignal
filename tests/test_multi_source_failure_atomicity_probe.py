"""Probe multi-source source-side atomicity when a later source fails."""
import sqlite3

import pytest

import source_runtime
from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor, record_source_result, source_health_contract
from source_metadata import get_source_metadata
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync

SOURCES = ("TED", "BASE")
IDS = {"TED": "multi-source-ted:1", "BASE": "multi-source-base:1"}


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _record(source, updated_at, actionable, status, title):
    return {
        "source": source,
        "external_id": IDS[source],
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


def _health(conn, source):
    return source_health_contract(conn, sources=[source])["items"][0]


def test_second_source_failure_rolls_back_first_source_and_degrades_both(monkeypatch):
    conn = _conn()
    discard_staged_source_syncs()

    for source in SOURCES:
        stage_source_sync(source, [_record(source, "2026-08-28T10:00:00Z", True, "active", f"{source} baseline")], f"{source}-cursor-baseline")
    first = commit_staged_source_syncs(conn)
    assert first == {
        "sources": 2,
        "signal_records": 2,
        "metadata_records": 2,
        "lifecycle_records": 2,
        "cursors": 2,
    }

    before_health = {}
    for source in SOURCES:
        record_source_result(conn, source, success=True, duration_ms=5, found=1, new_items=1)
        before_health[source] = _health(conn, source)
        assert before_health[source]["health"] == "healthy"

    real_persist_lifecycle = source_runtime.persist_lifecycle_observations

    def fail_second_source(conn_, records, *, commit=True):
        records = list(records or [])
        if records and records[0].get("source") == "BASE":
            raise sqlite3.OperationalError("injected second-source lifecycle failure")
        return real_persist_lifecycle(conn_, records, commit=commit)

    monkeypatch.setattr(source_runtime, "persist_lifecycle_observations", fail_second_source)

    stage_source_sync("TED", [_record("TED", "2026-08-28T11:00:00Z", False, "cancelled", "TED must rollback")], "TED-cursor-must-not-commit")
    stage_source_sync("BASE", [_record("BASE", "2026-08-28T11:00:00Z", False, "cancelled", "BASE must rollback")], "BASE-cursor-must-not-commit")

    with pytest.raises(sqlite3.OperationalError, match="injected second-source lifecycle failure"):
        commit_staged_source_syncs(conn)

    for source in SOURCES:
        signal = get_signal_record(conn, source, IDS[source])
        metadata = get_source_metadata(conn, source, IDS[source])
        lifecycle = lifecycle_for(conn, source, IDS[source])
        assert signal["title"] == f"{source} baseline"
        assert signal["source_updated_at"] == "2026-08-28T10:00:00Z"
        assert metadata["source_status"] == "active"
        assert metadata["source_updated_at"] == "2026-08-28T10:00:00Z"
        assert lifecycle["is_actionable"] == 1
        assert lifecycle["lifecycle_status"] == "active"
        assert get_source_cursor(conn, source) == f"{source}-cursor-baseline"

        after_health = _health(conn, source)
        assert after_health["health"] == "degraded"
        assert after_health["consecutive_failures"] == 1
        assert str(after_health["last_error"]).startswith("ingestion_commit_failed:OperationalError")
        assert after_health["last_success"] == before_health[source]["last_success"]

    assert commit_staged_source_syncs(conn) == {
        "sources": 0,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 0,
    }
