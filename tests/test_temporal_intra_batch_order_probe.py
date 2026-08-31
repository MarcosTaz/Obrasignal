"""Test-only probe: publisher chronology must beat list order inside one staged batch."""
import sqlite3

from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor
from source_metadata import get_source_metadata
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "ocds-intra-batch-temporal:lot:1"


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


def test_newer_publisher_truth_wins_even_when_older_duplicate_is_later_in_same_batch():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    discard_staged_source_syncs()

    newer = _record("2026-08-28T10:00:00Z", False, "cancelled", "newer publisher truth")
    older = _record("2026-08-28T09:00:00Z", True, "active", "older later in list")

    # Deliberately adversarial list order: newest causal observation first, stale
    # duplicate second. Arrival/list order must not manufacture publisher authority.
    stage_source_sync(SOURCE, [newer, older], "cursor-batch")
    commit_staged_source_syncs(conn)

    signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
    metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
    lifecycle = lifecycle_for(conn, SOURCE, EXTERNAL_ID)

    assert get_source_cursor(conn, SOURCE) == "cursor-batch"
    assert signal["title"] == "newer publisher truth"
    assert signal["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert metadata["source_status"] == "cancelled"
    assert metadata["source_updated_at"] == "2026-08-28T10:00:00Z"
    assert lifecycle["is_actionable"] == 0
    assert lifecycle["lifecycle_status"] == "cancelled"
    assert lifecycle["source_updated_at"] == "2026-08-28T10:00:00Z"
