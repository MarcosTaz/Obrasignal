import sqlite3

import pytest

from signal_store import (
    MAX_NORMALIZED_JSON_BYTES,
    ensure_signal_records,
    persist_signal_records,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_missing_identity_fails_closed():
    conn = _conn()
    with pytest.raises(ValueError, match="source is required"):
        persist_signal_records(conn, [{"external_id": "1"}])
    with pytest.raises(ValueError, match="external_id is required"):
        persist_signal_records(conn, [{"source": "A"}])


def test_staged_source_mismatch_fails_closed():
    conn = _conn()
    with pytest.raises(ValueError, match="staged source mismatch"):
        persist_signal_records(
            conn,
            [{"source": "OTHER", "external_id": "1"}],
            expected_source="EXPECTED",
        )


def test_unknown_type_and_non_mapping_fail_closed():
    conn = _conn()
    with pytest.raises(ValueError, match="unsupported signal_type"):
        persist_signal_records(
            conn,
            [{"source": "A", "external_id": "1", "signal_type": "UNKNOWN"}],
        )
    with pytest.raises(ValueError, match="must be a mapping"):
        persist_signal_records(conn, ["not-a-record"])


def test_snapshot_size_limit_blocks_unbounded_normalized_payload():
    conn = _conn()
    oversized = {
        "source": "A",
        "external_id": "big",
        "description": "x" * (MAX_NORMALIZED_JSON_BYTES + 100),
    }
    with pytest.raises(ValueError, match="snapshot exceeds safety limit"):
        persist_signal_records(conn, [oversized])


def test_schema_creation_is_idempotent_and_indexed():
    conn = _conn()
    ensure_signal_records(conn)
    ensure_signal_records(conn)
    indexes = {
        row["name"]
        for row in conn.execute("PRAGMA index_list(signal_records)").fetchall()
    }
    assert {
        "idx_signal_records_type_target",
        "idx_signal_records_source_updated",
        "idx_signal_records_country_type",
    }.issubset(indexes)
