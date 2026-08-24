import json
import sqlite3

import pytest

from signal_store import (
    ALLOWED_SIGNAL_TYPES,
    SIGNAL_SCHEMA_VERSION,
    get_signal_record,
    persist_signal_records,
    signal_type_of,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_signal_type_defaults_to_tender_and_rejects_unknown():
    assert signal_type_of({}) == "TENDER"
    assert signal_type_of({"signal_type": ""}) == "TENDER"
    assert signal_type_of({"signal_type": " procurement_plan "}) == "PROCUREMENT_PLAN"
    assert "ASSET_SIGNAL" in ALLOWED_SIGNAL_TYPES
    with pytest.raises(ValueError, match="unsupported signal_type"):
        signal_type_of({"signal_type": "NOT_A_SIGNAL"})


def test_procurement_plan_round_trips_with_provenance():
    conn = _conn()
    record = {
        "source": "BR_PNCP_PCA",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": "08241804000194:2026:1:975",
        "title": "Serviços de engenharia",
        "buyer": "Órgão público",
        "country": "BRA",
        "value": 17700000.0,
        "currency": "BRL",
        "target_date": "2026-12-23",
        "publication_date": "2025-05-13",
        "source_updated_at": "2026-05-03T12:27:41",
        "taxonomy": "PNCP_PCA_CATEGORY",
        "category_code": "8",
        "source_reference": "925377-31/2026",
        "publisher_native_category": "Obras e Serviços de Engenharia",
        "_runtime_hint": "exclude-me",
    }
    assert persist_signal_records(
        conn,
        [record],
        observed_at="2026-08-24T20:00:00+00:00",
        expected_source="BR_PNCP_PCA",
    ) == 1
    stored = get_signal_record(
        conn,
        "BR_PNCP_PCA",
        record["external_id"],
        "PROCUREMENT_PLAN",
    )
    assert stored["signal_schema_version"] == SIGNAL_SCHEMA_VERSION
    assert stored["target_date"] == "2026-12-23"
    assert stored["currency"] == "BRL"
    snapshot = json.loads(stored["normalized_json"])
    assert snapshot["signal_type"] == "PROCUREMENT_PLAN"
    assert snapshot["publisher_native_category"] == "Obras e Serviços de Engenharia"
    assert "_runtime_hint" not in snapshot


def test_idempotent_update_preserves_first_observed():
    conn = _conn()
    first = {"source": "TEST", "external_id": "1", "signal_type": "FORECAST", "title": "First"}
    second = {**first, "title": "Updated"}
    persist_signal_records(conn, [first], observed_at="2026-08-24T10:00:00Z")
    persist_signal_records(conn, [second], observed_at="2026-08-25T10:00:00Z")
    stored = get_signal_record(conn, "TEST", "1", "FORECAST")
    assert stored["title"] == "Updated"
    assert stored["first_observed"] == "2026-08-24T10:00:00Z"
    assert stored["last_observed"] == "2026-08-25T10:00:00Z"
    assert conn.execute("SELECT COUNT(*) FROM signal_records").fetchone()[0] == 1


def test_same_external_id_can_exist_across_signal_types():
    conn = _conn()
    assert persist_signal_records(conn, [
        {"source": "MIXED", "external_id": "abc", "signal_type": "TENDER"},
        {"source": "MIXED", "external_id": "abc", "signal_type": "AWARD"},
    ]) == 2
    assert get_signal_record(conn, "MIXED", "abc", "TENDER")
    assert get_signal_record(conn, "MIXED", "abc", "AWARD")
