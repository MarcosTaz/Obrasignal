import json
import sqlite3

from account_privacy import export_account_data, request_account_deletion
from account_registry import ensure_account
from company_profile import ensure_profile_table
from decision_log import ensure_decision_table
from evaluation_policy import ensure_evaluation_schema
from notification_events import ensure_event_table, register_push_device
from opportunity_workflow import ensure_workflow_table


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "account-a")
    ensure_account(conn, "account-b")
    ensure_profile_table(conn)
    ensure_decision_table(conn)
    ensure_event_table(conn)
    ensure_workflow_table(conn)
    ensure_evaluation_schema(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT)"
    )
    conn.execute(
        "INSERT OR REPLACE INTO tenders(id,source,external_id,title) VALUES(1,'TED','A-1','A'),(2,'TED','B-1','B')"
    )
    now = "2026-08-27T08:00:00+00:00"
    for account_id, tender_id in (("account-a", 1), ("account-b", 2)):
        conn.execute(
            "INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            (account_id, json.dumps({"account_id": account_id, "name": account_id}), now),
        )
        conn.execute(
            """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (account_id, f"{account_id}:event", tender_id, "TED", "new_high_match", 95, now),
        )
        register_push_device(
            conn,
            account_id,
            f"install-{account_id}",
            f"ExpoPushToken[{account_id}]",
            "android",
        )
        event_id = conn.execute(
            "SELECT id FROM opportunity_events WHERE account_id=? ORDER BY id DESC LIMIT 1",
            (account_id,),
        ).fetchone()[0]
        device_id = conn.execute(
            "SELECT id FROM push_devices WHERE account_id=? ORDER BY id DESC LIMIT 1",
            (account_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO push_deliveries(event_id,push_device_id,attempt_count,last_attempt_at) VALUES(?,?,1,?)",
            (event_id, device_id, now),
        )
    conn.commit()
    return conn


def test_account_export_consumes_notification_owner_contract_and_stays_tenant_safe():
    conn = _db()

    payload = export_account_data(conn, "account-a")
    encoded = json.dumps(payload, sort_keys=True)

    notification = payload["notification_delivery"]
    assert [row["installation_id"] for row in notification["push_devices"]] == ["install-account-a"]
    assert len(notification["push_deliveries"]) == 1
    assert "ExpoPushToken[account-a]" not in encoded
    assert "ExpoPushToken[account-b]" not in encoded
    assert "install-account-b" not in encoded
    assert notification["scope"]["export_status"] == "INCLUDE_SANITIZED"


def test_account_deletion_consumes_notification_cleanup_before_event_deletion_and_preserves_b():
    conn = _db()

    state = request_account_deletion(conn, "account-a")

    assert state["state"] == "PENDING"
    assert conn.execute(
        "SELECT COUNT(*) FROM push_devices WHERE account_id='account-a'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM push_devices WHERE account_id='account-b'"
    ).fetchone()[0] == 1
    assert conn.execute(
        """SELECT COUNT(*) FROM push_deliveries pd
           JOIN opportunity_events e ON e.id=pd.event_id
           WHERE e.account_id='account-b'"""
    ).fetchone()[0] == 1
    assert "push_deliveries" in state["server_cleanup"]["deleted_private_tables"]
    assert "push_devices" in state["server_cleanup"]["deleted_private_tables"]
