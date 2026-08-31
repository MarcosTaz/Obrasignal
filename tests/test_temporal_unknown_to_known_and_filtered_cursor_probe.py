"""Acceptance probes for temporal evidence improvement and filtered-record cursor semantics."""
import sqlite3

from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor
from source_metadata import get_source_metadata
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "ocds-temporal-improvement:lot:1"


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


def test_known_publisher_time_can_improve_existing_unknown_temporal_evidence():
    conn = _conn()
    discard_staged_source_syncs()

    unknown = _record(None, True, "active", "unknown chronology")
    known = _record("2026-08-28T09:00:00Z", False, "cancelled", "known chronology")

    stage_source_sync(SOURCE, [unknown], "cursor-unknown")
    first = commit_staged_source_syncs(conn)
    stage_source_sync(SOURCE, [known], "cursor-known")
    second = commit_staged_source_syncs(conn)

    assert first["signal_records"] == 1
    assert second["signal_records"] == 1
    assert second["metadata_records"] == 1
    assert second["lifecycle_records"] == 1
    assert get_source_cursor(conn, SOURCE) == "cursor-known"

    signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
    metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
    lifecycle = lifecycle_for(conn, SOURCE, EXTERNAL_ID)
    assert signal["title"] == "known chronology"
    assert signal["source_updated_at"] == "2026-08-28T09:00:00Z"
    assert metadata["source_status"] == "cancelled"
    assert metadata["source_updated_at"] == "2026-08-28T09:00:00Z"
    assert lifecycle["is_actionable"] == 0
    assert lifecycle["lifecycle_status"] == "cancelled"
    assert lifecycle["source_updated_at"] == "2026-08-28T09:00:00Z"


def test_filtered_stale_record_advances_cursor_without_mutating_canonical_truth():
    conn = _conn()
    discard_staged_source_syncs()

    newer = _record("2026-08-28T10:00:00Z", False, "cancelled", "newer canonical")
    older = _record("2026-08-28T09:00:00Z", True, "active", "older late arrival")

    stage_source_sync(SOURCE, [newer], "cursor-newer")
    commit_staged_source_syncs(conn)
    stage_source_sync(SOURCE, [older], "cursor-after-filter")
    second = commit_staged_source_syncs(conn)

    assert second["signal_records"] == 0
    assert second["metadata_records"] == 0
    assert second["lifecycle_records"] == 0
    assert second["cursors"] == 1
    assert get_source_cursor(conn, SOURCE) == "cursor-after-filter"

    signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
    metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
    lifecycle = lifecycle_for(conn, SOURCE, EXTERNAL_ID)
    assert signal["title"] == "newer canonical"
    assert signal["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert metadata["source_status"] == "cancelled"
    assert lifecycle["is_actionable"] == 0
    assert lifecycle["lifecycle_status"] == "cancelled"
