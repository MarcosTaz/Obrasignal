"""Persistence verifier for the isolated #277/#335 E2E fixture SQLite store.

This module is evidence only: e2e_fixture_api remains the schema/data owner.
The fixture database is deliberately separate from canonical ObraSignal storage.
"""
from __future__ import annotations

import sqlite3

from storage_contract import StorageContractError, TableContract, verify_schema


FIXTURE_STORE_CONTRACTS: dict[str, TableContract] = {
    "e2e_opportunity_fixtures": TableContract(
        "E2E fixture / e2e_fixture_api",
        frozenset({
            "fixture_id", "account_id", "run_id", "source", "external_id", "created_at",
        }),
        tenant_column="account_id",
        unique_keys=(("fixture_id",), ("account_id", "run_id"), ("account_id", "source", "external_id")),
        required_indexes=("idx_e2e_fixture_account_run",),
    ),
    "opportunity_workflow": TableContract(
        "opportunity_workflow (reused inside isolated fixture store)",
        frozenset({"id", "account_id", "source", "external_id", "status", "note", "updated_at"}),
        tenant_column="account_id",
        unique_keys=(("account_id", "source", "external_id"),),
    ),
}

_FIXTURE_SOURCE = "OBRASIGNAL_E2E_FIXTURE"


def verify_fixture_store(conn: sqlite3.Connection) -> None:
    """Verify structure and the fixture->workflow tenant ownership chain."""
    verify_schema(conn, FIXTURE_STORE_CONTRACTS)
    mismatch = int(conn.execute(
        """SELECT COUNT(*)
           FROM opportunity_workflow w
           JOIN e2e_opportunity_fixtures f
             ON f.source=w.source AND f.external_id=w.external_id
           WHERE f.account_id<>w.account_id"""
    ).fetchone()[0])
    orphan = int(conn.execute(
        """SELECT COUNT(*)
           FROM opportunity_workflow w
           LEFT JOIN e2e_opportunity_fixtures f
             ON f.account_id=w.account_id AND f.source=w.source AND f.external_id=w.external_id
           WHERE w.source=? AND f.fixture_id IS NULL""",
        (_FIXTURE_SOURCE,),
    ).fetchone()[0])
    errors: list[str] = []
    if mismatch:
        errors.append(f"workflow_tenant_mismatch_rows={mismatch}")
    if orphan:
        errors.append(f"orphan_fixture_workflow_rows={orphan}")
    if errors:
        raise StorageContractError("fixture store integrity failed: " + "; ".join(errors))


def fixture_tenant_owned_tables() -> dict[str, str]:
    return {
        table: contract.tenant_column
        for table, contract in FIXTURE_STORE_CONTRACTS.items()
        if contract.tenant_column is not None
    }
