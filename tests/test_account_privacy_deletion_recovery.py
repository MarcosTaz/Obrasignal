import json
import sqlite3

import account_privacy
from account_privacy import deletion_state, export_account_data, request_account_deletion
from account_registry import ensure_account
from company_profile import ensure_profile_table
from decision_log import ensure_decision_table
from evaluation_policy import ensure_evaluation_schema
from notification_events import ensure_event_table
from opportunity_workflow import ensure_workflow_table


def _open(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed(path):
    conn = _open(path)
    ensure_account(conn, "tenant-a")
    ensure_account(conn, "tenant-b")
    ensure_profile_table(conn)
    ensure_decision_table(conn)
    ensure_event_table(conn)
    ensure_workflow_table(conn)
    ensure_evaluation_schema(conn)
    now = "2026-08-25T20:00:00+00:00"
    for tenant in ("tenant-a", "tenant-b"):
        conn.execute(
            "INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            (tenant, json.dumps({"name": tenant}), now),
        )
        conn.execute(
            """INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at)
               VALUES(?,?,?,?,?,?)""",
            (tenant, "TEST", "O-1", "REVIEWING", tenant, now),
        )
    conn.commit()
    return conn


def test_retry_resumes_pending_deletion_after_interrupted_partial_cleanup(tmp_path):
    conn = _seed(tmp_path / "privacy-recovery.db")

    # Model a process dying after the durable pending marker and after only one
    # dependent cleanup step. A subsequent customer retry must resume safely.
    conn.execute("DELETE FROM company_profiles WHERE account_id='tenant-a'")
    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id='tenant-a'")
    conn.commit()

    state = request_account_deletion(conn, "tenant-a")

    assert state["state"] == "PENDING"
    assert state["product_private_db_deleted"] is True
    assert state["external_revocation"] == "PENDING"
    for table in account_privacy.DEPENDENT_PRIVATE_TABLES:
        assert conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE account_id='tenant-a'"
        ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM company_profiles WHERE account_id='tenant-b'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM opportunity_workflow WHERE account_id='tenant-b'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT status FROM accounts WHERE account_id='tenant-a'"
    ).fetchone()[0] == "deleted_pending_revocation"

    # A repeated request remains idempotent and cannot regress or recreate data.
    repeated = request_account_deletion(conn, "tenant-a")
    assert repeated["state"] == "PENDING"
    assert repeated["product_private_db_deleted"] is True
    for table in account_privacy.DEPENDENT_PRIVATE_TABLES:
        assert conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE account_id='tenant-a'"
        ).fetchone()[0] == 0
    conn.close()


def test_raw_deleted_status_is_not_treated_as_external_revocation_proof(tmp_path):
    conn = _seed(tmp_path / "privacy-unproven-completion.db")
    conn.execute("UPDATE accounts SET status='deleted' WHERE account_id='tenant-a'")
    conn.commit()

    state = deletion_state(conn, "tenant-a")
    assert state["state"] == "UNKNOWN"
    assert state["product_private_db_deleted"] is None
    assert state["external_revocation"] == "UNKNOWN"
    assert state["reason"] == "deletion_completion_evidence_unavailable"

    # A retry converts the unproven marker into the known server-cleaned PENDING
    # state instead of preserving a false COMPLETED claim.
    recovered = request_account_deletion(conn, "tenant-a")
    assert recovered["state"] == "PENDING"
    assert recovered["product_private_db_deleted"] is True
    assert recovered["external_revocation"] == "PENDING"
    conn.close()


def test_export_uses_one_read_snapshot_across_concurrent_workflow_write(tmp_path, monkeypatch):
    path = tmp_path / "privacy-export-snapshot.db"
    seeded = _seed(path)
    seeded.execute("PRAGMA journal_mode=WAL")
    seeded.close()

    reader = _open(path)
    reader.execute("PRAGMA journal_mode=WAL")
    original_rows = account_privacy._rows
    raced = {"done": False}

    def rows_with_concurrent_write(conn, sql, params=()):
        if not raced["done"] and "opportunity_decisions" in sql:
            raced["done"] = True
            writer = _open(path)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute(
                    "UPDATE opportunity_workflow SET note='AFTER-SNAPSHOT' WHERE account_id='tenant-a'"
                )
                writer.commit()
            finally:
                writer.close()
        return original_rows(conn, sql, params)

    monkeypatch.setattr(account_privacy, "_rows", rows_with_concurrent_write)
    payload = export_account_data(reader, "tenant-a")
    reader.close()

    assert raced["done"] is True
    assert payload["snapshot"]["boundary"] == "SQLITE_READ_TRANSACTION"
    assert payload["opportunity_workflow"][0]["note"] == "tenant-a"
    with _open(path) as check:
        assert check.execute(
            "SELECT note FROM opportunity_workflow WHERE account_id='tenant-a'"
        ).fetchone()[0] == "AFTER-SNAPSHOT"
