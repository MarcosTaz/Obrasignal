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


def _company_state_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE company_state_snapshots (
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
        CREATE INDEX idx_company_state_account_version
            ON company_state_snapshots(account_id, state_version DESC);
        """
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
    verify_schema(conn, PREBUILD_CONTRACTS)

    conn.execute("DROP INDEX idx_company_state_account_version")
    with pytest.raises(StorageContractError, match="missing_index=idx_company_state_account_version"):
        verify_schema(conn, PREBUILD_CONTRACTS)


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
