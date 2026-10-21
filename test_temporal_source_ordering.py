import sqlite3

from opportunity_lifecycle import lifecycle_for
from signal_store import get_signal_record
from source_health import ensure_source_health, get_source_cursor
from source_metadata import get_source_metadata
from source_runtime import (
    _aware_source_instant,
    commit_staged_source_syncs,
    discard_staged_source_syncs,
    stage_source_sync,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _uk_lifecycle_record(*, updated_at, actionable, status, title):
    return {
        "source": "UK_PROCUREMENT",
        "external_id": "ocds-temporal:lot:1",
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


def test_late_older_source_observation_cannot_resurrect_newer_lifecycle_state():
    conn = _conn()
    discard_staged_source_syncs()
    newer = _uk_lifecycle_record(
        updated_at="2026-08-24T12:00:00Z",
        actionable=False,
        status="cancelled",
        title="Newer cancelled state",
    )
    older = _uk_lifecycle_record(
        updated_at="2026-08-24T11:00:00Z",
        actionable=True,
        status="active",
        title="Older active state",
    )

    stage_source_sync("UK_PROCUREMENT", [newer], "cursor-newer")
    first = commit_staged_source_syncs(conn)
    assert first["signal_records"] == 1
    assert first["metadata_records"] == 1
    assert first["lifecycle_records"] == 1

    # Arrival order is deliberately reversed: the older publisher state is seen
    # after the newer cancellation. Processing time must not give it authority.
    stage_source_sync("UK_PROCUREMENT", [older], "cursor-later-arrival")
    second = commit_staged_source_syncs(conn)

    assert second["signal_records"] == 0
    assert second["metadata_records"] == 0
    assert second["lifecycle_records"] == 0
    assert get_source_cursor(conn, "UK_PROCUREMENT") == "cursor-later-arrival"

    signal = get_signal_record(conn, "UK_PROCUREMENT", "ocds-temporal:lot:1")
    metadata = get_source_metadata(conn, "UK_PROCUREMENT", "ocds-temporal:lot:1")
    lifecycle = lifecycle_for(conn, "UK_PROCUREMENT", "ocds-temporal:lot:1")
    assert signal["title"] == "Newer cancelled state"
    assert signal["source_updated_at"] == "2026-08-24T12:00:00Z"
    assert metadata["source_status"] == "cancelled"
    assert metadata["source_updated_at"] == "2026-08-24T12:00:00Z"
    assert lifecycle["is_actionable"] == 0
    assert lifecycle["lifecycle_status"] == "cancelled"
    assert lifecycle["source_updated_at"] == "2026-08-24T12:00:00Z"


def test_source_ordering_guard_does_not_invent_timezone_for_naive_timestamp():
    assert _aware_source_instant("2026-08-24T12:00:00") is None
