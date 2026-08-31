import sqlite3

import pytest

from notification_events import ensure_event_table, register_push_device
from notification_privacy_lifecycle import (
    NotificationPrivacyContractError,
    delete_notification_account_data,
    export_notification_account_data,
)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY,status TEXT NOT NULL)")
    conn.execute("INSERT INTO accounts(account_id,status) VALUES ('account-a','active'),('account-b','active')")
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
        buyer TEXT, country TEXT, url TEXT, deadline TEXT, publication_date TEXT,
        score INTEGER, first_seen TEXT
    )""")
    ensure_event_table(conn)
    return conn


def _event(conn, account_id, tender_id):
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (?,?,?,?,'2099-01-01',95,datetime('now'))",
        (tender_id, "TED", f"{account_id}-{tender_id}", f"Private {account_id}"),
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES (?,?,?,'TED','new_high_match',95,datetime('now'))""",
        (account_id, f"{account_id}:{tender_id}", tender_id),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _device(conn, account_id, suffix):
    register_push_device(
        conn,
        account_id,
        f"install-{suffix}",
        f"ExpoPushToken[token-{suffix}]",
        "android",
    )
    return conn.execute(
        "SELECT id FROM push_devices WHERE account_id=?",
        (account_id,),
    ).fetchone()[0]


def _delivery(conn, event_id, device_id):
    conn.execute(
        """INSERT INTO push_deliveries(event_id,push_device_id,attempt_count,last_attempt_at)
           VALUES (?,?,1,datetime('now'))""",
        (event_id, device_id),
    )


def test_notification_export_is_strictly_tenant_scoped_and_sanitized():
    conn = _db()
    event_a = _event(conn, "account-a", 1)
    event_b = _event(conn, "account-b", 2)
    device_a = _device(conn, "account-a", "a")
    device_b = _device(conn, "account-b", "b")
    _delivery(conn, event_a, device_a)
    _delivery(conn, event_b, device_b)

    exported = export_notification_account_data(conn, "account-a")

    assert [row["installation_id"] for row in exported["push_devices"]] == ["install-a"]
    assert len(exported["push_deliveries"]) == 1
    assert "expo_push_token" not in exported["push_devices"][0]
    assert "account_id" not in exported["push_devices"][0]
    assert exported["scope"]["provider_acceptance_is_delivery"] is False


def test_cross_tenant_delivery_chain_blocks_export_instead_of_disclosing_other_tenant():
    conn = _db()
    event_a = _event(conn, "account-a", 1)
    device_b = _device(conn, "account-b", "b")
    _delivery(conn, event_a, device_b)

    with pytest.raises(NotificationPrivacyContractError, match="cross_account_chain"):
        export_notification_account_data(conn, "account-a")


def test_deleting_account_a_notification_state_preserves_account_b():
    conn = _db()
    event_a = _event(conn, "account-a", 1)
    event_b = _event(conn, "account-b", 2)
    device_a = _device(conn, "account-a", "a")
    device_b = _device(conn, "account-b", "b")
    _delivery(conn, event_a, device_a)
    _delivery(conn, event_b, device_b)

    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id='account-a'")
    delete_notification_account_data(conn, "account-a")

    assert conn.execute("SELECT COUNT(*) FROM push_devices WHERE account_id='account-a'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM push_devices WHERE account_id='account-b'").fetchone()[0] == 1
    assert conn.execute(
        """SELECT COUNT(*) FROM push_deliveries pd
           JOIN opportunity_events e ON e.id=pd.event_id
           WHERE e.account_id='account-b'"""
    ).fetchone()[0] == 1
