"""Privacy-lifecycle regressions owned by Notification Delivery."""
import sqlite3

import pytest

from app import APP
from notification_events import (
    ensure_event_table,
    reconcile_push_receipts,
    register_push_device,
    submit_pending_pushes,
    unregister_push_device,
)
from notification_privacy_lifecycle import (
    NotificationPrivacyContractError,
    assert_notification_account_cleanup_postconditions,
    delete_notification_account_data,
    export_notification_account_data,
    notification_account_accepts_new_binding,
)


def _conn():
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


def _file_conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _event(conn, *, account_id="account-a", tender_id=1, suffix="A-1"):
    conn.execute(
        "INSERT OR IGNORE INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (?,?,?,?,?,?,datetime('now'))",
        (tender_id, "TED", suffix, f"Private {suffix}", "2099-01-01", 95),
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES (?,?,?,'TED','new_high_match',95,datetime('now'))""",
        (account_id, f"{account_id}:ted:{suffix.lower()}", tender_id),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _accepted(ticket_id="ticket-a"):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"status": "ok", "id": ticket_id}]}

    return Response()


def _receipt(payload):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": payload}

    return Response()


def _seed_delivery(conn, *, installation="install-private-001", token="ExpoPushToken[private-token]"):
    event_id = _event(conn)
    registered = register_push_device(conn, "account-a", installation, token, "android")
    assert registered["binding_id"]
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("ticket-private")) == 1
    device_id = conn.execute("SELECT id FROM push_devices WHERE account_id='account-a'").fetchone()[0]
    delivery_id = conn.execute("SELECT id FROM push_deliveries WHERE event_id=?", (event_id,)).fetchone()[0]
    return event_id, device_id, delivery_id


def test_export_includes_sanitized_device_and_delivery_truth_without_routing_credentials():
    conn = _conn()
    _seed_delivery(conn)
    assert reconcile_push_receipts(
        conn,
        "account-a",
        min_age_seconds=0,
        post=lambda *_args, **_kwargs: _receipt({"ticket-private": {"status": "ok"}}),
    ) == 1

    payload = export_notification_account_data(conn, "account-a")
    assert payload["scope"]["export_status"] == "INCLUDE_SANITIZED"
    assert payload["scope"]["provider_acceptance_is_delivery"] is False
    assert len(payload["push_devices"]) == 1
    assert len(payload["push_deliveries"]) == 1

    device = payload["push_devices"][0]
    assert device["installation_id"] == "install-private-001"
    assert device["provider_token_present"] is True
    assert device["tap_binding_present"] is True
    assert "expo_push_token" not in device
    assert "binding_id" not in device
    assert "account_id" not in device

    delivery = payload["push_deliveries"][0]
    assert delivery["provider_ticket_present"] is True
    assert delivery["receipt_status"] == "provider_accepted"
    assert "ticket_id" not in delivery
    assert "expo_push_token" not in delivery
    conn.close()


def test_cleanup_deletes_delivery_before_device_and_requires_privacy_deletion_pending():
    conn = _conn()
    _seed_delivery(conn)
    conn.execute(
        """CREATE TRIGGER delivery_before_device_delete
           BEFORE DELETE ON push_devices
           WHEN EXISTS(SELECT 1 FROM push_deliveries WHERE push_device_id=OLD.id)
           BEGIN SELECT RAISE(ABORT,'delivery_must_delete_first'); END"""
    )

    with pytest.raises(NotificationPrivacyContractError, match="requires_deletion_pending"):
        delete_notification_account_data(conn, "account-a")
    assert conn.execute("SELECT COUNT(*) FROM push_devices WHERE account_id='account-a'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM push_deliveries").fetchone()[0] == 1

    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id='account-a'")
    result = delete_notification_account_data(conn, "account-a")
    assert result["cleanup_order"] == [
        "push_deliveries",
        "push_devices",
        "opportunity_events_by_privacy_owner",
    ]
    assert result["deleted_push_deliveries"] == 1
    assert result["deleted_push_devices"] == 1
    assert result["retention"] == "NO_TIME_BASED_RETENTION_ASSERTED"
    assert_notification_account_cleanup_postconditions(conn, "account-a")
    # Notification owner intentionally leaves canonical opportunity_events to Privacy.
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events WHERE account_id='account-a'").fetchone()[0] == 1
    conn.close()


def test_late_provider_receipt_and_retry_cannot_recreate_local_state_after_cleanup():
    conn = _conn()
    _seed_delivery(conn)
    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id='account-a'")
    delete_notification_account_data(conn, "account-a")
    conn.execute("UPDATE accounts SET status='deleted_pending_revocation' WHERE account_id='account-a'")

    provider_calls = []

    def forbidden_provider(*_args, **_kwargs):
        provider_calls.append(True)
        raise AssertionError("provider must not be called after notification cleanup")

    assert reconcile_push_receipts(conn, "account-a", min_age_seconds=0, post=forbidden_provider) == 0
    assert submit_pending_pushes(conn, "account-a", post=forbidden_provider) == 0
    assert provider_calls == []
    assert conn.execute("SELECT COUNT(*) FROM push_deliveries").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM push_devices WHERE account_id='account-a'").fetchone()[0] == 0
    conn.close()


def test_dead_token_tombstone_is_retained_for_active_dedupe_but_deleted_with_account():
    conn = _conn()
    _event(conn)
    register_push_device(conn, "account-a", "install-dead-001", "ExpoPushToken[dead-one]", "android")
    device_id = conn.execute("SELECT id FROM push_devices WHERE account_id='account-a'").fetchone()[0]
    assert unregister_push_device(conn, "account-a", "install-dead-001") is True
    tombstone = conn.execute(
        "SELECT id,expo_push_token,revoked_at FROM push_devices WHERE account_id='account-a'"
    ).fetchone()
    assert tombstone["id"] == device_id
    assert tombstone["expo_push_token"].startswith("revoked:")
    assert tombstone["revoked_at"]

    exported = export_notification_account_data(conn, "account-a")
    assert exported["push_devices"][0]["revoked_at"]
    assert "expo_push_token" not in exported["push_devices"][0]

    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id='account-a'")
    result = delete_notification_account_data(conn, "account-a")
    assert result["dead_token_tombstone"] == "RETAIN_WHILE_ACCOUNT_EXISTS_DELETE_WITH_ACCOUNT"
    assert conn.execute("SELECT COUNT(*) FROM push_devices WHERE id=?", (device_id,)).fetchone()[0] == 0
    conn.close()


def test_cross_account_delivery_chain_blocks_cleanup_instead_of_orphaning_other_tenant():
    conn = _conn()
    event_id = _event(conn, account_id="account-a", tender_id=1, suffix="A-X")
    register_push_device(conn, "account-b", "install-b-cross", "ExpoPushToken[token-b-cross]", "android")
    device_b = conn.execute("SELECT id FROM push_devices WHERE account_id='account-b'").fetchone()[0]
    conn.execute(
        """INSERT INTO push_deliveries(event_id,push_device_id,attempt_count,last_attempt_at)
           VALUES (?,?,1,datetime('now'))""",
        (event_id, device_b),
    )
    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id='account-a'")

    with pytest.raises(NotificationPrivacyContractError, match="cross_account_chain"):
        delete_notification_account_data(conn, "account-a")
    assert conn.execute("SELECT COUNT(*) FROM push_deliveries").fetchone()[0] == 1
    assert conn.execute("SELECT account_id FROM push_devices WHERE id=?", (device_b,)).fetchone()[0] == "account-b"
    conn.close()


def test_deleted_account_push_route_cannot_rebind_or_regain_notification_ownership(monkeypatch, tmp_path):
    db_path = tmp_path / "notification-deleted.db"
    conn = _file_conn(db_path)
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY,status TEXT NOT NULL)")
    conn.execute("INSERT INTO accounts(account_id,status) VALUES ('account-a','deleted_pending_revocation')")
    conn.commit()
    assert notification_account_accepts_new_binding(conn, "account-a") is False
    conn.close()

    APP.config["OBRASIGNAL_DB_CONNECT"] = lambda: _file_conn(db_path)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    try:
        response = APP.test_client().post(
            "/api/v1/push/devices",
            json={
                "installation_id": "install-after-delete-001",
                "expo_push_token": "ExpoPushToken[after-delete]",
                "platform": "android",
            },
        )
        assert response.status_code == 410
        assert response.get_json()["error"] == "account_notification_lifecycle_block"
        assert response.get_json()["notification_registration_allowed"] is False

        check = _file_conn(db_path)
        tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "push_devices" in tables:
            assert check.execute("SELECT COUNT(*) FROM push_devices WHERE account_id='account-a'").fetchone()[0] == 0
        check.close()
    finally:
        APP.config.pop("OBRASIGNAL_DB_CONNECT", None)
