from __future__ import annotations

import hashlib
import json
import sqlite3

from .store import EarnedCashStore


_TABLES = (
    "earnedcash_companies",
    "earnedcash_customers",
    "earnedcash_projects",
    "earnedcash_contracts",
    "earnedcash_cases",
    "earnedcash_cash_receipts",
    "earnedcash_audit_events",
)


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _quoted(identifier: str) -> str:
    if identifier not in _TABLES and not identifier.replace("_", "").isalnum():
        raise ValueError("invalid sqlite identifier")
    return '"' + identifier.replace('"', '""') + '"'


def database_fingerprint(connection: sqlite3.Connection) -> str:
    """Return a deterministic digest of the EarnedCash persistence surface only."""
    payload: dict[str, object] = {}
    for table in _TABLES:
        if not _table_exists(connection, table):
            payload[table] = None
            continue
        info = connection.execute(f"PRAGMA table_info({_quoted(table)})").fetchall()
        columns = [str(row[1]) for row in info]
        if not columns:
            payload[table] = []
            continue
        select_columns = ", ".join(_quoted(column) for column in columns)
        order_columns = ", ".join(_quoted(column) for column in columns)
        rows = connection.execute(
            f"SELECT {select_columns} FROM {_quoted(table)} ORDER BY {order_columns}"
        ).fetchall()
        payload[table] = [list(row) for row in rows]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def copy_database(
    source: sqlite3.Connection, destination: sqlite3.Connection
) -> str:
    """Copy a caller-owned SQLite database and return the copied fingerprint."""
    if source is destination:
        raise ValueError("backup_source_and_destination_must_differ")
    source.backup(destination)
    return database_fingerprint(destination)


def restore_verified_copy(
    backup_source: sqlite3.Connection,
    destination: sqlite3.Connection,
    *,
    tenant_ids: tuple[str, ...],
) -> str:
    """Restore into a caller-provided destination and fail closed on drift/tamper.

    This function intentionally does not locate, open, or overwrite any production
    database. The caller must supply both SQLite connections explicitly.
    """
    if backup_source is destination:
        raise ValueError("restore_source_and_destination_must_differ")
    expected = database_fingerprint(backup_source)
    backup_source.backup(destination)
    observed = database_fingerprint(destination)
    if observed != expected:
        raise RuntimeError("restored_database_fingerprint_mismatch")

    restored = EarnedCashStore(destination)
    for tenant_id in tenant_ids:
        if not restored.audit_valid(tenant_id):
            raise RuntimeError(f"restored_audit_invalid:{tenant_id}")

    final = database_fingerprint(destination)
    if final != expected:
        raise RuntimeError("restore_verification_mutated_database")
    return final
