"""Probe fail-closed semantics when conflicting observations share publisher time."""
import sqlite3

from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor
from source_metadata import get_source_metadata
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync

SOURCE = "TED"
EXTERNAL_ID = "equal-time:1"
STAMP = "2026-08-28T12:00:00Z"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _record(title, status, actionable):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "taxonomy": "CPV",
        "category_code": "45200000",
        "source_status": status,
        "source_updated_at": STAMP,
        "is_actionable": actionable,
        "lifecycle_status": status,
        "lifecycle_reason": f"publisher reports {status}",
    }


def test_equal_publisher_time_conflict_cannot_replace_canonical_truth():
    conn = _conn()
    discard_staged_source_syncs()

    stage_source_sync(SOURCE, [_record("first observed truth", "active", True)], "cursor-a")
    assert commit_staged_source_syncs(conn)["signal_records"] == 1

    stage_source_sync(SOURCE, [_record("conflicting equal-time truth", "cancelled", False)], "cursor-b")
    second = commit_staged_source_syncs(conn)

    assert second == {
        "sources": 1,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 1,
    }

    signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
    metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
    lifecycle = lifecycle_for(conn, SOURCE, EXTERNAL_ID)

    assert signal["title"] == "first observed truth"
    assert signal["source_updated_at"] == STAMP
    assert metadata["source_status"] == "active"
    assert metadata["source_updated_at"] == STAMP
    assert lifecycle["is_actionable"] == 1
    assert lifecycle["lifecycle_status"] == "active"

    # Equal publisher instants establish no causal winner. Fetch progress can move
    # independently, but canonical business truth must remain unchanged.
    assert get_source_cursor(conn, SOURCE) == "cursor-b"
