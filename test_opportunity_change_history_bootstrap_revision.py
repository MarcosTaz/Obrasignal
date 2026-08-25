import sqlite3

from opportunity_change_history import get_change_history, persist_change_observations
from signal_store import persist_signal_records


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _record(amendment_number):
    return {
        "source": "BOOTSTRAP_AMENDMENT_SOURCE",
        "signal_type": "TENDER",
        "external_id": "BOOT-1",
        "title": "Stable opportunity",
        "deadline": "2026-10-01T12:00:00Z",
        "source_status": "Open",
        "amendment_number": amendment_number,
        "source_reference": "BOOT-1",
    }


def test_existing_signal_amendment_is_reconstructed_as_previous_source_version():
    conn = _conn()
    persist_signal_records(
        conn,
        [_record("2")],
        observed_at="2026-08-24T09:00:00Z",
    )

    result = persist_change_observations(
        conn,
        [_record("3")],
        observed_at="2026-08-25T09:00:00Z",
    )

    assert result["snapshots"] == 2
    assert result["change_sets"] == 1
    item = get_change_history(conn, "BOOTSTRAP_AMENDMENT_SOURCE", "BOOT-1")[0]
    assert item["native_revision"] == "3"
    assert item["changed_fields"] == ["source_version"]
    assert item["changes"][0]["old_value"] == "2"
    assert item["changes"][0]["new_value"] == "3"
