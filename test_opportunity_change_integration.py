import sqlite3

from capability_registry import capability, enabled_capabilities
from opportunity_change_history import get_change_history
from source_health import ensure_source_health
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _canada(deadline, amendment_number, amendment_date):
    return {
        "source": "CA_CANADABUYS",
        "signal_type": "TENDER",
        "external_id": "W1234-26TEST",
        "title": "Construction services",
        "deadline": deadline,
        "source_status": "Open",
        "source_reference": "REF-123",
        "amendment_number": amendment_number,
        "amendment_date": amendment_date,
        "is_actionable": True,
        "lifecycle_status": "open",
    }


def test_change_history_is_pilot_without_promoting_enabled_capabilities():
    spec = capability("OPPORTUNITY_CHANGE_HISTORY")
    assert spec.state == "PILOT"
    assert spec.dependencies == ("SIGNAL",)
    assert spec.feature_flag == "opportunity_change_history_v0"
    assert "opportunity.changed" in spec.publishes_events
    assert enabled_capabilities() == ("SIGNAL",)


def test_source_runtime_preserves_canadabuys_native_amendment_identity():
    conn = _conn()
    discard_staged_source_syncs()
    stage_source_sync(
        "CA_CANADABUYS",
        [_canada("2026-09-10T17:00:00Z", "0", "2026-08-24T12:00:00Z")],
        "cursor-a",
    )
    commit_staged_source_syncs(conn)

    stage_source_sync(
        "CA_CANADABUYS",
        [_canada("2026-09-17T17:00:00Z", "3", "2026-08-25T12:00:00Z")],
        "cursor-b",
    )
    commit_staged_source_syncs(conn)

    item = get_change_history(conn, "CA_CANADABUYS", "W1234-26TEST")[0]
    assert item["native_revision"] == "3"
    assert item["source_updated_at"] == "2026-08-25T12:00:00Z"
    assert item["source_ref"] == "REF-123"
    assert item["changed_fields"] == ["deadline"]
    assert item["changes"][0]["detail"] == "EXTENDED"
