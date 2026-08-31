import sqlite3

import pytest

from decision_log import ensure_decision_table
from storage_contract import STARTUP_CONTRACTS, StorageContractError, table_columns, verify_schema


LEGACY_SCHEMA = """CREATE TABLE opportunity_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    score INTEGER,
    features_json TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    decided_at TEXT NOT NULL
)"""


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_partial_historical_decision_schema_migrates_to_full_authority_contract():
    conn = _conn()
    conn.execute(LEGACY_SCHEMA)

    ensure_decision_table(conn)

    columns = set(table_columns(conn, "opportunity_decisions"))
    assert {"account_id", "profile_fingerprint", "opportunity_fingerprint"} <= columns
    verify_schema(conn, {"opportunity_decisions": STARTUP_CONTRACTS["opportunity_decisions"]})
    conn.close()


def test_storage_verifier_fails_closed_before_authority_migration_runs():
    conn = _conn()
    conn.execute(LEGACY_SCHEMA)

    with pytest.raises(StorageContractError) as exc:
        verify_schema(conn, {"opportunity_decisions": STARTUP_CONTRACTS["opportunity_decisions"]})

    message = str(exc.value)
    assert "profile_fingerprint" in message
    assert "opportunity_fingerprint" in message
    conn.close()
