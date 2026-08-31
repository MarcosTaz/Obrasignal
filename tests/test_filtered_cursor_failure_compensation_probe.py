"""Failing-boundary probe for cursor failure after temporal filtering.

A stale observation may be filtered from canonical writes, but cursor persistence is
still part of the same source-side transaction. If cursor persistence fails, the
existing canonical truth and prior cursor must survive while Source Health records
that durable ingestion did not complete.
"""
import sqlite3

import pytest

import source_runtime
from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import (
    ensure_source_health,
    get_source_cursor,
    record_source_result,
    source_health_contract,
)
from source_metadata import get_source_metadata
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "ocds-filtered-cursor-failure:lot:1"


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


def _health_item(conn):
    contract = source_health_contract(conn, sources=[SOURCE])
    return contract["items"][0]


def test_filtered_stale_record_cursor_failure_rolls_back_and_degrades_health(monkeypatch):
    conn = _conn()
    discard_staged_source_syncs()

    newer = _record("2026-08-28T10:00:00Z", False, "cancelled", "newer canonical")
    stale = _record("2026-08-28T09:00:00Z", True, "active", "stale late arrival")

    stage_source_sync(SOURCE, [newer], "cursor-canonical")
    first = commit_staged_source_syncs(conn)
    assert first["signal_records"] == 1
    assert get_source_cursor(conn, SOURCE) == "cursor-canonical"

    # Represent transport/fetch success separately from durable ingestion success.
    record_source_result(conn, SOURCE, success=True, duration_ms=5, found=1, new_items=1)
    before_health = _health_item(conn)
    assert before_health["health"] == "healthy"
    assert before_health["consecutive_failures"] == 0

    original_set_source_cursor = source_runtime.set_source_cursor

    def fail_cursor_write(conn_, source, watermark, *, commit=True, observed_at=None):
        if watermark == "cursor-must-not-commit":
            raise sqlite3.OperationalError("injected cursor persistence failure")
        return original_set_source_cursor(
            conn_, source, watermark, commit=commit, observed_at=observed_at
        )

    monkeypatch.setattr(source_runtime, "set_source_cursor", fail_cursor_write)

    stage_source_sync(SOURCE, [stale], "cursor-must-not-commit")
    with pytest.raises(sqlite3.OperationalError, match="injected cursor persistence failure"):
        commit_staged_source_syncs(conn)

    # Cursor progress is not allowed to survive a failed source-side transaction.
    assert get_source_cursor(conn, SOURCE) == "cursor-canonical"

    # The stale observation was filtered and cannot mutate any canonical projection.
    signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
    metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
    lifecycle = lifecycle_for(conn, SOURCE, EXTERNAL_ID)
    assert signal["title"] == "newer canonical"
    assert signal["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert metadata["source_status"] == "cancelled"
    assert metadata["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert lifecycle["is_actionable"] == 0
    assert lifecycle["lifecycle_status"] == "cancelled"

    # Fetch success must not be misrepresented as durable ingestion success.
    after_health = _health_item(conn)
    assert after_health["health"] == "degraded"
    assert after_health["consecutive_failures"] == 1
    assert str(after_health["last_error"]).startswith("ingestion_commit_failed:OperationalError")
    assert after_health["last_success"] == before_health["last_success"]

    # Staged work must not leak into a later commit attempt.
    assert commit_staged_source_syncs(conn) == {
        "sources": 0,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 0,
    }
