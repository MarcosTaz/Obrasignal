"""Failing-before probe for partial Source Health compensation."""
import sqlite3

import pytest

import source_runtime
from source_health import ensure_source_health, record_source_result, source_health_contract
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync

SOURCES = ("TED", "BASE")


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _record(source):
    return {
        "source": source,
        "external_id": f"compensation-failure:{source.lower()}:1",
        "signal_type": "TENDER",
        "title": f"{source} observation",
        "taxonomy": "CPV",
        "category_code": "45200000",
        "source_status": "active",
        "source_updated_at": "2026-08-28T12:00:00Z",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def _health(conn, source):
    return source_health_contract(conn, sources=[source])["items"][0]


def test_health_compensation_failure_does_not_skip_remaining_staged_sources(monkeypatch):
    conn = _conn()
    discard_staged_source_syncs()

    for source in SOURCES:
        record_source_result(conn, source, success=True, duration_ms=5, found=1, new_items=1)
        assert _health(conn, source)["health"] == "healthy"
        stage_source_sync(source, [_record(source)], f"{source}-cursor-new")

    real_lifecycle = source_runtime.persist_lifecycle_observations

    def fail_original_commit(conn_, records, *, commit=True):
        records = list(records or [])
        if records and records[0].get("source") == "BASE":
            raise sqlite3.OperationalError("injected canonical persistence failure")
        return real_lifecycle(conn_, records, commit=commit)

    monkeypatch.setattr(source_runtime, "persist_lifecycle_observations", fail_original_commit)

    real_compensate = source_runtime.record_source_ingestion_failure
    attempted = []

    def fail_first_compensation(conn_, source, *, error=None):
        attempted.append(source)
        if source == "TED":
            raise RuntimeError("injected health compensation failure")
        return real_compensate(conn_, source, error=error)

    monkeypatch.setattr(source_runtime, "record_source_ingestion_failure", fail_first_compensation)

    with pytest.raises(RuntimeError, match="source health compensation failed") as caught:
        commit_staged_source_syncs(conn)

    assert isinstance(caught.value.__cause__, sqlite3.OperationalError)
    assert "injected canonical persistence failure" in str(caught.value.__cause__)

    # One failed health write must not prevent best-effort compensation of the
    # remaining staged sources. Otherwise fetch-success truth survives for BASE
    # even though its canonical persistence transaction was rolled back.
    assert attempted == ["TED", "BASE"]
    assert _health(conn, "BASE")["health"] == "degraded"
    assert _health(conn, "BASE")["consecutive_failures"] == 1
    assert str(_health(conn, "BASE")["last_error"]).startswith(
        "ingestion_commit_failed:OperationalError"
    )

    # TED compensation was deliberately made unavailable, so no false claim is
    # made that its health row was durably degraded.
    assert _health(conn, "TED")["health"] == "healthy"

    # Staging must still be cleared even when both the canonical transaction and
    # one compensation write fail.
    assert commit_staged_source_syncs(conn) == {
        "sources": 0,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 0,
    }
