"""Failing-before probe for Watchlist persistence on the current trust spine.

This is acceptance-only. It does not implement Watchlist or duplicate the shared
migration lock owned by Persistence #238.
"""

import sqlite3

import opportunity_workflow as workflow


def _conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def test_watchlist_schema_has_additive_priority_and_saved_at_contract():
    conn = _conn()
    workflow.ensure_workflow_table(conn)
    columns = {row[1]: row for row in conn.execute("PRAGMA table_info(opportunity_workflow)")}
    assert "priority" in columns
    assert columns["priority"][3] == 1  # NOT NULL
    assert columns["priority"][4] == "'NORMAL'"
    assert "saved_at" in columns

    indexes = {row[1] for row in conn.execute("PRAGMA index_list(opportunity_workflow)")}
    assert "idx_opportunity_workflow_account_saved" in indexes
    assert "idx_opportunity_workflow_account_status_priority" in indexes


def test_watchlist_migration_preserves_existing_rows_and_is_rerunnable():
    conn = _conn()
    conn.execute(
        """CREATE TABLE opportunity_workflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, source, external_id)
        )"""
    )
    conn.execute(
        "INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at) VALUES (?,?,?,?,?,?)",
        ("tenant-a", "TED", "legacy-1", "REVIEWING", "keep me", "2026-08-27T00:00:00+00:00"),
    )
    conn.commit()

    workflow.ensure_workflow_table(conn)
    workflow.ensure_workflow_table(conn)

    row = conn.execute(
        "SELECT account_id,source,external_id,status,note,priority,saved_at FROM opportunity_workflow"
    ).fetchone()
    assert dict(row) == {
        "account_id": "tenant-a",
        "source": "TED",
        "external_id": "legacy-1",
        "status": "REVIEWING",
        "note": "keep me",
        "priority": "NORMAL",
        "saved_at": None,
    }


def test_watchlist_contract_exposes_saved_membership_without_coercing_existing_workflow():
    conn = _conn()
    workflow.ensure_workflow_table(conn)
    current = workflow.get_workflow(conn, "tenant-a", "TED", "x")
    assert current["status"] == "NEW"
    assert current["priority"] == "NORMAL"
    assert current["saved_at"] is None
    assert current["is_saved"] is False


def test_watchlist_status_vocabulary_includes_dismissed():
    assert "DISMISSED" in workflow.STATUSES
