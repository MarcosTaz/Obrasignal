from datetime import datetime, timezone
import sqlite3

import pytest

from company_state import CompanyState, CompanyStateError
from company_state_store import (
    CompanyStateService,
    CompanyStateStorageError,
    ensure_company_state_schema,
    save_company_state,
)

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_existing_schema_with_columns_but_without_version_uniqueness_fails_closed():
    conn = make_conn()
    conn.execute(
        """CREATE TABLE company_state_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            state_version INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            contract_version TEXT NOT NULL,
            as_of TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    with pytest.raises(CompanyStateStorageError, match="schema is incompatible"):
        ensure_company_state_schema(conn)


def test_corrupt_current_row_during_save_rolls_back_transaction():
    conn = make_conn()
    ensure_company_state_schema(conn)
    conn.execute(
        """INSERT INTO company_state_snapshots(
            account_id,state_version,fingerprint,contract_version,as_of,snapshot_json,created_at
        ) VALUES(?,?,?,?,?,?,?)""",
        ("a", 1, "bad", "company-state.v1", NOW.isoformat(), "{bad", NOW.isoformat()),
    )
    conn.commit()

    with pytest.raises(CompanyStateStorageError):
        save_company_state(conn, CompanyState("a", NOW, ()), expected_version=1, clock=NOW)
    assert conn.in_transaction is False


def test_trusted_provider_empty_or_non_iterable_batch_is_controlled_error():
    service = CompanyStateService(make_conn)
    with pytest.raises(CompanyStateError, match="cannot be empty"):
        service.ingest_trusted_facts("a", [], clock=NOW)
    with pytest.raises(CompanyStateError, match="must be iterable"):
        service.ingest_trusted_facts("a", None, clock=NOW)
