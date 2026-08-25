import sqlite3

import pytest

import opportunity_change_history as history
from opportunity_change_history import (
    CHANGE_SCHEMA_VERSION,
    DIFF_POLICY_VERSION,
    MATERIAL,
    NORMALIZER_VERSION,
    build_monitored_state,
    content_fingerprint,
    detect_changes,
    get_change_history,
    opportunity_changed_event,
    persist_change_observations,
)


NOW_A = "2026-08-24T09:00:00+00:00"
NOW_B = "2026-08-25T09:00:00+00:00"
NOW_C = "2026-08-26T09:00:00+00:00"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _record(**overrides):
    record = {
        "source": "TEST_SOURCE",
        "signal_type": "TENDER",
        "external_id": "opp-1",
        "title": "Construction services",
        "description": "Build a civic facility",
        "buyer": "City Council",
        "place": "Lisbon",
        "value": "2000000.00",
        "currency": "EUR",
        "deadline": "2026-09-10T12:00:00Z",
        "source_status": "OPEN",
        "source_reference": "notice-1",
        "source_updated_at": "2026-08-24T08:00:00Z",
        "documents": [{"id": "spec", "title": "Specification"}],
        "lots": [{"id": "lot-1", "title": "Main works"}],
    }
    record.update(overrides)
    return record


def _changes(conn):
    return get_change_history(conn, "TEST_SOURCE", "opp-1")


def test_identical_state_creates_baseline_only_then_no_change():
    conn = _conn()
    first = persist_change_observations(conn, [_record()], observed_at=NOW_A)
    second = persist_change_observations(conn, [_record()], observed_at=NOW_B)
    assert first == {"snapshots": 1, "change_sets": 0, "changes": 0}
    assert second == {"snapshots": 0, "change_sets": 0, "changes": 0}
    assert _changes(conn) == []


def test_deadline_extended_and_shortened_are_two_real_changes():
    conn = _conn()
    persist_change_observations(conn, [_record()], observed_at=NOW_A)
    persist_change_observations(conn, [_record(deadline="2026-09-17T12:00:00Z")], observed_at=NOW_B)
    persist_change_observations(conn, [_record(deadline="2026-09-10T12:00:00Z")], observed_at=NOW_C)
    items = _changes(conn)
    assert len(items) == 2
    assert items[0]["changes"][0]["detail"] == "SHORTENED"
    assert items[1]["changes"][0]["detail"] == "EXTENDED"
    assert all(item["materiality"] == MATERIAL for item in items)


def test_date_formats_normalize_to_same_semantics():
    a = build_monitored_state(_record(deadline="01/09/2026"))
    b = build_monitored_state(_record(deadline="2026-09-01"))
    assert a["deadline"] == b["deadline"] == "2026-09-01"
    assert content_fingerprint(a) == content_fingerprint(b)


def test_value_change_and_currency_change_are_detected_separately():
    previous = build_monitored_state(_record(value="2000000", currency="EUR"))
    changed_value = build_monitored_state(_record(value="2500000.0", currency="EUR"))
    fields = {c["field"] for c in detect_changes(previous, changed_value)}
    assert fields == {"value"}
    changed_currency = build_monitored_state(_record(value="2000000.00", currency="GBP"))
    fields = {c["field"] for c in detect_changes(previous, changed_currency)}
    assert fields == {"currency"}


def test_status_change_is_material():
    previous = build_monitored_state(_record(source_status="OPEN"))
    current = build_monitored_state(_record(source_status="CANCELLED"))
    change = detect_changes(previous, current)[0]
    assert change["field"] == "source_status"
    assert change["materiality"] == MATERIAL


def test_title_whitespace_and_case_noise_is_ignored_but_real_change_is_not():
    previous = build_monitored_state(_record(title="Construction services"))
    whitespace = build_monitored_state(_record(title="  Construction   services  "))
    case = build_monitored_state(_record(title="CONSTRUCTION SERVICES"))
    real = build_monitored_state(_record(title="Construction and maintenance services"))
    assert detect_changes(previous, whitespace) == []
    assert detect_changes(previous, case) == []
    assert [c["field"] for c in detect_changes(previous, real)] == ["title"]


def test_collection_order_only_change_is_ignored():
    docs_a = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]
    docs_b = list(reversed(docs_a))
    previous = build_monitored_state(_record(documents=docs_a))
    current = build_monitored_state(_record(documents=docs_b))
    assert detect_changes(previous, current) == []


def test_collection_item_added_and_removed():
    previous = build_monitored_state(_record(documents=[{"id": "a", "title": "A"}]))
    added = build_monitored_state(_record(documents=[{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]))
    add_change = detect_changes(previous, added)
    assert add_change[0]["change_type"] == "ITEM_ADDED"
    removed = build_monitored_state(_record(documents=[]))
    remove_change = detect_changes(previous, removed)
    assert remove_change[0]["change_type"] == "ITEM_REMOVED"


def test_lot_added_is_grouped_in_one_change_set_with_other_fields():
    conn = _conn()
    persist_change_observations(conn, [_record()], observed_at=NOW_A)
    changed = _record(
        deadline="2026-09-17T12:00:00Z",
        lots=[{"id": "lot-1", "title": "Main works"}, {"id": "lot-2", "title": "Electrical"}],
    )
    result = persist_change_observations(conn, [changed], observed_at=NOW_B)
    assert result["change_sets"] == 1
    item = _changes(conn)[0]
    assert set(item["changed_fields"]) == {"deadline", "lots"}
    assert {change["change_type"] for change in item["changes"]} == {"CHANGED", "ITEM_ADDED"}


def test_missing_field_is_carried_forward_but_explicit_null_is_a_change():
    previous = build_monitored_state(_record(buyer="City Council"))
    missing_record = _record()
    missing_record.pop("buyer")
    carried = build_monitored_state(missing_record, previous)
    assert carried["buyer"] == previous["buyer"]
    assert detect_changes(previous, carried) == []
    explicit_null = build_monitored_state(_record(buyer=None), previous)
    changes = detect_changes(previous, explicit_null)
    assert [c["field"] for c in changes] == ["buyer"]


def test_same_update_processed_twice_creates_one_change_set():
    conn = _conn()
    persist_change_observations(conn, [_record()], observed_at=NOW_A)
    version_b = _record(value="2500000")
    first = persist_change_observations(conn, [version_b], observed_at=NOW_B)
    second = persist_change_observations(conn, [version_b], observed_at=NOW_C)
    assert first["change_sets"] == 1
    assert second == {"snapshots": 0, "change_sets": 0, "changes": 0}
    assert len(_changes(conn)) == 1


def test_native_amendment_source_ref_and_versions_are_preserved():
    conn = _conn()
    persist_change_observations(conn, [_record(source_version="v1")], observed_at=NOW_A)
    persist_change_observations(
        conn,
        [_record(source_version="amendment-3", source_reference="notice-amendment-3", value="2500000")],
        observed_at=NOW_B,
    )
    item = _changes(conn)[0]
    assert item["native_revision"] == "amendment-3"
    assert item["source_ref"] == "notice-amendment-3"
    assert item["diff_policy_version"] == DIFF_POLICY_VERSION
    assert item["schema_version"] == CHANGE_SCHEMA_VERSION
    snapshot = conn.execute("SELECT normalizer_version FROM opportunity_snapshots ORDER BY snapshot_id DESC LIMIT 1").fetchone()
    assert snapshot["normalizer_version"] == NORMALIZER_VERSION


def test_fingerprint_is_deterministic_and_excludes_observation_time():
    state = build_monitored_state(_record())
    assert content_fingerprint(state) == content_fingerprint(dict(reversed(list(state.items()))))
    conn = _conn()
    persist_change_observations(conn, [_record()], observed_at=NOW_A)
    result = persist_change_observations(conn, [_record()], observed_at=NOW_C)
    assert result["snapshots"] == 0


def test_material_only_read_model_and_event_payload():
    conn = _conn()
    persist_change_observations(conn, [_record()], observed_at=NOW_A)
    persist_change_observations(conn, [_record(value="2500000")], observed_at=NOW_B)
    item = get_change_history(conn, "TEST_SOURCE", "opp-1", material_only=True)[0]
    event = opportunity_changed_event(item)
    assert event == {
        "event_type": "opportunity.changed",
        "event_version": 1,
        "opportunity_id": {"source": "TEST_SOURCE", "signal_type": "TENDER", "external_id": "opp-1"},
        "change_set_id": item["change_set_id"],
        "changed_fields": ["value"],
        "materiality": MATERIAL,
    }


def test_history_failure_can_be_rolled_back_by_transaction_owner(monkeypatch):
    conn = _conn()
    conn.execute("CREATE TABLE marker(value TEXT)")
    conn.commit()
    original = history.ensure_change_history_tables

    def fail_after_schema(target_conn):
        original(target_conn)
        target_conn.execute("INSERT INTO marker(value) VALUES('partial')")
        raise RuntimeError("history persistence failed")

    monkeypatch.setattr(history, "ensure_change_history_tables", fail_after_schema)
    with pytest.raises(RuntimeError, match="history persistence failed"):
        try:
            persist_change_observations(conn, [_record()], commit=False)
        except Exception:
            conn.rollback()
            raise
    assert conn.execute("SELECT COUNT(*) FROM marker").fetchone()[0] == 0
