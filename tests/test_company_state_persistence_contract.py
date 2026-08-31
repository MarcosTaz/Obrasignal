import concurrent.futures
import json
import sqlite3

import pytest

from storage_contract import (
    KNOWN_TABLE_OWNERS,
    PREBUILD_CONTRACTS,
    StorageContractError,
    contract_fingerprint,
    tenant_owned_tables,
    verify_json_integrity,
    verify_schema,
)
from storage_migration_lock import run_serialized_schema_init
from storage_recovery import create_backup_artifact, verified_restore_drill


COMPANY_STATE_PREBUILD = {
    "company_state_snapshots": PREBUILD_CONTRACTS["company_state_snapshots"],
}


def _company_state_schema(conn: sqlite3.Connection) -> None:
    # Mirror the #240 owner schema without importing/copying its storage writer.
    # This file tests the #238 persistence contract only; company_state_store.py
    # remains the sole schema/data owner when that prebuild is composed.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS company_state_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            state_version INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            contract_version TEXT NOT NULL,
            as_of TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(account_id, state_version)
        );
        CREATE INDEX IF NOT EXISTS idx_company_state_account_version
            ON company_state_snapshots(account_id, state_version DESC);
        """
    )


def _insert_snapshot(
    conn: sqlite3.Connection,
    account_id: str,
    state_version: int,
    marker: str,
) -> None:
    payload = json.dumps(
        {"account_id": account_id, "marker": marker},
        sort_keys=True,
        separators=(",", ":"),
    )
    conn.execute(
        """INSERT INTO company_state_snapshots(
               account_id,state_version,fingerprint,contract_version,as_of,snapshot_json,created_at
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            account_id,
            state_version,
            f"fp-{marker}",
            "company-state.v1",
            "2026-08-25T00:00:00+00:00",
            payload,
            "2026-08-25T00:00:00+00:00",
        ),
    )


def test_company_state_prebuild_contract_is_exact_and_noncanonical_by_default():
    contract = PREBUILD_CONTRACTS["company_state_snapshots"]
    assert KNOWN_TABLE_OWNERS["company_state_snapshots"] is contract
    assert contract.owner == "Company State / company_state_store"
    assert contract.tenant_column == "account_id"
    assert contract.required_columns == frozenset({
        "id", "account_id", "state_version", "fingerprint", "contract_version",
        "as_of", "snapshot_json", "created_at",
    })
    assert contract.unique_keys == (("account_id", "state_version"),)
    assert contract.required_indexes == ("idx_company_state_account_version",)

    # Registration must not silently promote the prebuild into the current-main
    # contract fingerprint or tenant map. Integration must opt in explicitly.
    assert contract_fingerprint(include_runtime=True) != contract_fingerprint(
        include_runtime=True, include_prebuild=True
    )
    assert "company_state_snapshots" not in tenant_owned_tables()
    assert tenant_owned_tables(include_prebuild=True)["company_state_snapshots"] == "account_id"


def test_company_state_prebuild_schema_verifies_owner_columns_unique_and_index():
    conn = sqlite3.connect(":memory:")
    _company_state_schema(conn)
    verify_schema(conn, COMPANY_STATE_PREBUILD)

    conn.execute("DROP INDEX idx_company_state_account_version")
    with pytest.raises(StorageContractError, match="missing_index=idx_company_state_account_version"):
        verify_schema(conn, COMPANY_STATE_PREBUILD)


def test_company_state_prebuild_first_startup_is_serialized_and_rerunnable(tmp_path):
    path = tmp_path / "company-state.db"

    def initialize(_=None):
        conn = sqlite3.connect(path, timeout=30)
        try:
            _company_state_schema(conn)
            conn.commit()
        finally:
            conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(lambda n: (run_serialized_schema_init(initialize, path), True)[1], range(24)))

    conn = sqlite3.connect(path)
    try:
        verify_schema(conn, COMPANY_STATE_PREBUILD)
    finally:
        conn.close()


def test_company_state_prebuild_tenant_identity_and_version_are_isolated(tmp_path):
    path = tmp_path / "tenant-state.db"
    conn = sqlite3.connect(path)
    _company_state_schema(conn)
    _insert_snapshot(conn, "tenant-a", 1, "a-private")
    _insert_snapshot(conn, "tenant-b", 1, "b-private")
    conn.commit()

    rows_a = conn.execute(
        "SELECT account_id,state_version,snapshot_json FROM company_state_snapshots WHERE account_id=?",
        ("tenant-a",),
    ).fetchall()
    rows_b = conn.execute(
        "SELECT account_id,state_version,snapshot_json FROM company_state_snapshots WHERE account_id=?",
        ("tenant-b",),
    ).fetchall()
    assert len(rows_a) == 1 and rows_a[0][0:2] == ("tenant-a", 1)
    assert len(rows_b) == 1 and rows_b[0][0:2] == ("tenant-b", 1)
    assert "a-private" in rows_a[0][2] and "b-private" not in rows_a[0][2]
    assert "b-private" in rows_b[0][2] and "a-private" not in rows_b[0][2]

    # Same state_version is legitimate across accounts but not within one account.
    with pytest.raises(sqlite3.IntegrityError):
        _insert_snapshot(conn, "tenant-a", 1, "duplicate")
    conn.rollback()
    verify_schema(conn, COMPANY_STATE_PREBUILD)
    conn.close()


def test_company_state_snapshot_json_is_fail_closed_when_present():
    conn = sqlite3.connect(":memory:")
    _company_state_schema(conn)
    conn.execute(
        """INSERT INTO company_state_snapshots(
               account_id,state_version,fingerprint,contract_version,as_of,snapshot_json,created_at
           ) VALUES('tenant-a',1,'fp','company-state.v1','2026-08-25T00:00:00+00:00','{bad','2026-08-25T00:00:00+00:00')"""
    )
    with pytest.raises(StorageContractError, match="company_state_snapshots.snapshot_json:invalid_json_rows=1"):
        verify_json_integrity(conn)


def test_company_state_prebuild_is_preserved_by_verified_backup_restore(tmp_path):
    source = tmp_path / "company-state-source.db"
    conn = sqlite3.connect(source)
    _company_state_schema(conn)
    _insert_snapshot(conn, "tenant-a", 1, "a-private")
    _insert_snapshot(conn, "tenant-b", 1, "b-private")
    conn.commit()
    conn.close()

    artifact = create_backup_artifact(
        source,
        tmp_path / "backup",
        label="company-state-contract",
        source_revision="prebuild-contract-test",
    )
    # PREBUILD remains opt-in contract truth even though the physical SQLite
    # backup correctly preserves the table and rows.
    assert artifact["expected_contract_fingerprint"] == contract_fingerprint(include_runtime=True)

    restored = tmp_path / "company-state-restored.db"
    verified_restore_drill(artifact["artifact"], artifact["manifest"], restored)

    conn = sqlite3.connect(restored)
    try:
        verify_schema(conn, COMPANY_STATE_PREBUILD)
        verify_json_integrity(conn)
        rows = conn.execute(
            "SELECT account_id,state_version,snapshot_json FROM company_state_snapshots ORDER BY account_id,state_version"
        ).fetchall()
        assert [row[0:2] for row in rows] == [("tenant-a", 1), ("tenant-b", 1)]
        assert "a-private" in rows[0][2] and "b-private" not in rows[0][2]
        assert "b-private" in rows[1][2] and "a-private" not in rows[1][2]
    finally:
        conn.close()
