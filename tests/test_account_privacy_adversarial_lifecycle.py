import json
import sqlite3

import pytest

from account_privacy import (
    AccountDataContractError,
    AccountDeletionError,
    request_account_deletion,
)
from account_privacy_integrity import account_privacy_integrity_report
from account_registry import ensure_account
from company_profile import ensure_profile_table
from decision_log import ensure_decision_table
from evaluation_policy import ensure_evaluation_schema
from notification_events import ensure_event_table
from opportunity_workflow import ensure_workflow_table


def _conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed(path):
    conn = _conn(path)
    ensure_account(conn, "tenant-a")
    ensure_profile_table(conn)
    ensure_decision_table(conn)
    ensure_event_table(conn)
    ensure_workflow_table(conn)
    ensure_evaluation_schema(conn)
    now = "2026-08-25T20:00:00+00:00"
    conn.execute(
        "INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
        ("tenant-a", json.dumps({"private": "A"}), now),
    )
    conn.execute(
        "INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at) VALUES(?,?,?,?,?,?)",
        ("tenant-a", "PUBLIC", "1", "REVIEWING", "A", now),
    )
    conn.commit()
    return conn


def test_duplicate_deletion_request_is_idempotent_and_never_returns_active(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    first = request_account_deletion(conn, "tenant-a")
    second = request_account_deletion(conn, "tenant-a")
    status = conn.execute("SELECT status FROM accounts WHERE account_id='tenant-a'").fetchone()[0]
    assert first["state"] == "PENDING"
    assert second["state"] == "PENDING"
    assert status == "deleted_pending_revocation"
    conn.close()


def test_retry_after_contract_failure_can_only_reenter_deletion_not_active(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    conn.execute("CREATE TABLE future_private_state(account_id TEXT NOT NULL, secret TEXT)")
    conn.execute("INSERT INTO future_private_state VALUES('tenant-a','x')")
    conn.commit()
    with pytest.raises(AccountDataContractError):
        request_account_deletion(conn, "tenant-a")
    assert conn.execute("SELECT status FROM accounts WHERE account_id='tenant-a'").fetchone()[0] == "deletion_failed"
    conn.execute("DROP TABLE future_private_state")
    conn.commit()
    state = request_account_deletion(conn, "tenant-a")
    assert state["state"] == "PENDING"
    assert conn.execute("SELECT status FROM accounts WHERE account_id='tenant-a'").fetchone()[0] == "deleted_pending_revocation"
    conn.close()


def test_mid_scrub_database_abort_rolls_back_private_rows_and_reports_failed(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    conn.execute(
        "CREATE TRIGGER abort_workflow_delete BEFORE DELETE ON opportunity_workflow "
        "WHEN OLD.account_id='tenant-a' BEGIN SELECT RAISE(ABORT, 'synthetic_mid_scrub_crash'); END"
    )
    conn.commit()
    with pytest.raises(AccountDeletionError):
        request_account_deletion(conn, "tenant-a")
    assert conn.execute("SELECT status FROM accounts WHERE account_id='tenant-a'").fetchone()[0] == "deletion_failed"
    assert conn.execute("SELECT COUNT(*) FROM company_profiles WHERE account_id='tenant-a'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM opportunity_workflow WHERE account_id='tenant-a'").fetchone()[0] == 1
    conn.close()


def test_local_scrub_success_remains_partial_until_external_revocation(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    state = request_account_deletion(conn, "tenant-a")
    assert state["state"] == "PENDING"
    assert state["product_private_db_deleted"] is True
    assert state["external_revocation"] == "PENDING"
    assert conn.execute("SELECT status FROM accounts WHERE account_id='tenant-a'").fetchone()[0] == "deleted_pending_revocation"
    conn.close()


def test_integrity_detects_direct_orphan_without_deleting_it():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE company_profiles(account_id TEXT, profile_json TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO company_profiles VALUES('missing','{}','now')")
    report = account_privacy_integrity_report(conn)
    assert any(item["kind"] == "ORPHAN_ACCOUNT_REFERENCE" and item["table"] == "company_profiles" for item in report["findings"])
    assert conn.execute("SELECT COUNT(*) FROM company_profiles").fetchone()[0] == 1


def test_integrity_detects_cross_tenant_transitive_delivery_chain_as_critical():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE accounts(account_id TEXT PRIMARY KEY);
        INSERT INTO accounts VALUES('A');
        INSERT INTO accounts VALUES('B');
        CREATE TABLE opportunity_events(id INTEGER PRIMARY KEY, account_id TEXT);
        CREATE TABLE push_devices(id INTEGER PRIMARY KEY, account_id TEXT);
        CREATE TABLE push_deliveries(id INTEGER PRIMARY KEY, event_id INTEGER, push_device_id INTEGER);
        INSERT INTO opportunity_events VALUES(1,'A');
        INSERT INTO push_devices VALUES(2,'B');
        INSERT INTO push_deliveries VALUES(3,1,2);
        """
    )
    report = account_privacy_integrity_report(conn)
    assert any(item["kind"] == "CROSS_TENANT_TRANSITIVE_MISMATCH" and item["classification"] == "CRITICAL" for item in report["findings"])
    assert report["complete_for_customer_claim"] is False


def test_known_unresolved_prebuild_owner_contracts_keep_completeness_false():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO accounts VALUES('A')")
    conn.execute("CREATE TABLE company_state_snapshots(id INTEGER PRIMARY KEY, account_id TEXT)")
    report = account_privacy_integrity_report(conn)
    assert "company_state_snapshots" in report["unresolved_owner_contracts"]
    assert report["complete_for_customer_claim"] is False
