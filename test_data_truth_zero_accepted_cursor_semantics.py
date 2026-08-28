"""Probe cursor semantics when temporal authority rejects every fetched record."""
import sqlite3

from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync
from source_metadata import get_source_metadata
from opportunity_lifecycle import lifecycle_for

SOURCE = "TED"
EXTERNAL_ID = "zero-accepted:1"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _record(updated_at, title, status="active", actionable=True):
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


def test_zero_accepted_stale_records_preserve_canonical_truth_but_advance_fetch_cursor():
    conn = _conn()
    discard_staged_source_syncs()

    stage_source_sync(SOURCE, [_record("2026-08-28T12:00:00Z", "authoritative")], "cursor-12")
    first = commit_staged_source_syncs(conn)
    assert first == {
        "sources": 1,
        "signal_records": 1,
        "metadata_records": 1,
        "lifecycle_records": 1,
        "cursors": 1,
    }

    stage_source_sync(
        SOURCE,
        [_record("2026-08-28T11:00:00Z", "stale must not overwrite", status="cancelled", actionable=False)],
        "cursor-13",
    )
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

    assert signal["title"] == "authoritative"
    assert signal["source_updated_at"] == "2026-08-28T12:00:00Z"
    assert metadata["source_status"] == "active"
    assert metadata["source_updated_at"] == "2026-08-28T12:00:00Z"
    assert lifecycle["is_actionable"] == 1
    assert lifecycle["lifecycle_status"] == "active"

    # Cursor is fetch progress, not accepted-record count. A successfully processed
    # source page may advance its watermark even when every observation is rejected
    # as temporally non-authoritative; otherwise the same stale page can be replayed
    # indefinitely despite canonical truth remaining fail-closed.
    assert get_source_cursor(conn, SOURCE) == "cursor-13"
