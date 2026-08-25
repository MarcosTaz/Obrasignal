import sqlite3
from types import SimpleNamespace

import source_runtime as runtime
from capability_registry import capability, enabled_capabilities
from opportunity_change_history import get_change_history
from source_health import ensure_source_health


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


def _generic_revision(version):
    return {
        "source": "TEST_REVISION_SOURCE",
        "signal_type": "TENDER",
        "external_id": "REV-1",
        "title": "Stable title",
        "deadline": "2026-09-30T12:00:00Z",
        "source_status": "Open",
        "source_reference": "REV-1",
        "revision_id": version,
        "is_actionable": True,
        "lifecycle_status": "open",
    }


def _enable_history_for_test(monkeypatch):
    monkeypatch.setattr(runtime, "capability", lambda name: SimpleNamespace(state="PILOT"))


def test_change_history_is_research_gated_without_promoting_enabled_capabilities():
    spec = capability("OPPORTUNITY_CHANGE_HISTORY")
    assert spec.state == "RESEARCH"
    assert spec.dependencies == ("SIGNAL",)
    assert spec.feature_flag == "opportunity_change_history_v0"
    assert "opportunity.changed" in spec.publishes_events
    assert enabled_capabilities() == ("SIGNAL",)


def test_source_runtime_preserves_canadabuys_native_amendment_identity_when_deliberately_activated(monkeypatch):
    _enable_history_for_test(monkeypatch)
    conn = _conn()
    runtime.discard_staged_source_syncs()
    runtime.stage_source_sync(
        "CA_CANADABUYS",
        [_canada("2026-09-10T17:00:00Z", "0", "2026-08-24T12:00:00Z")],
        "cursor-a",
    )
    runtime.commit_staged_source_syncs(conn)

    runtime.stage_source_sync(
        "CA_CANADABUYS",
        [_canada("2026-09-17T17:00:00Z", "3", "2026-08-25T12:00:00Z")],
        "cursor-b",
    )
    runtime.commit_staged_source_syncs(conn)

    item = get_change_history(conn, "CA_CANADABUYS", "W1234-26TEST")[0]
    assert item["native_revision"] == "3"
    assert item["source_updated_at"] == "2026-08-25T12:00:00Z"
    assert item["source_ref"] == "REF-123"
    assert item["changed_fields"] == ["deadline", "source_version"]
    deadline = next(change for change in item["changes"] if change["field"] == "deadline")
    assert deadline["detail"] == "EXTENDED"


def test_source_runtime_preserves_revision_only_publisher_change_when_deliberately_activated(monkeypatch):
    _enable_history_for_test(monkeypatch)
    conn = _conn()
    runtime.discard_staged_source_syncs()
    runtime.stage_source_sync("TEST_REVISION_SOURCE", [_generic_revision("r1")], "cursor-r1")
    runtime.commit_staged_source_syncs(conn)

    runtime.stage_source_sync("TEST_REVISION_SOURCE", [_generic_revision("r2")], "cursor-r2")
    runtime.commit_staged_source_syncs(conn)

    history = get_change_history(conn, "TEST_REVISION_SOURCE", "REV-1")
    assert len(history) == 1
    item = history[0]
    assert item["native_revision"] == "r2"
    assert item["changed_fields"] == ["source_version"]
    assert item["changes"][0]["old_value"] == "r1"
    assert item["changes"][0]["new_value"] == "r2"
