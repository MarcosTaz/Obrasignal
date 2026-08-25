"""Regression coverage for account-scoped remote notification delivery."""
import sqlite3

from app import APP
from notification_events import (
    ensure_event_table,
    register_push_device,
    submit_pending_pushes,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
        buyer TEXT, country TEXT, url TEXT, deadline TEXT, score INTEGER,
        first_seen TEXT
    )""")
    ensure_event_table(conn)
    return conn


def _file_conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _accepted(ticket_id="ticket-a"):
    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": [{"status": "ok", "id": ticket_id}]}
    return Response()


def test_device_rebind_moves_installation_from_account_a_to_b_without_changing_device_identity():
    conn = _conn()
    first = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    first_id = conn.execute("SELECT id FROM push_devices WHERE installation_id='install-device-001'").fetchone()[0]
    again = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    assert again["binding_id"] == first["binding_id"]

    second = register_push_device(conn, "account-b", "install-device-001", "ExpoPushToken[token-a]", "android")
    assert second["binding_id"] != first["binding_id"]
    rows = conn.execute("SELECT id,account_id,installation_id,expo_push_token FROM push_devices").fetchall()
    assert [tuple(row) for row in rows] == [(first_id, "account-b", "install-device-001", "ExpoPushToken[token-a]")]
    conn.close()


def test_push_device_api_uses_request_identity_and_account_scoped_delete(monkeypatch, tmp_path):
    db_path = tmp_path / "push-api.db"
    APP.config["OBRASIGNAL_DB_CONNECT"] = lambda: _file_conn(db_path)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    try:
        client = APP.test_client()
        response = client.post(
            "/api/v1/push/devices",
            json={
                "account_id": "account-b",
                "installation_id": "install-device-api-001",
                "expo_push_token": "ExpoPushToken[api-token]",
                "platform": "android",
            },
        )
        assert response.status_code == 200
        assert response.get_json()["binding_id"]

        conn = _file_conn(db_path)
        row = conn.execute("SELECT account_id,installation_id FROM push_devices").fetchone()
        conn.close()
        assert tuple(row) == ("account-a", "install-device-api-001")

        monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-b")
        response = client.delete(
            "/api/v1/push/devices",
            json={"installation_id": "install-device-api-001"},
        )
        assert response.status_code == 200
        assert response.get_json()["removed"] is False
        conn = _file_conn(db_path)
        assert conn.execute("SELECT account_id FROM push_devices").fetchone()[0] == "account-a"
        conn.close()
    finally:
        APP.config.pop("OBRASIGNAL_DB_CONNECT", None)


def test_push_submission_is_account_scoped_idempotent_tray_safe_and_token_rotation_safe():
    conn = _conn()
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (1,'TED','A-1','Obra A confidencial','2099-01-01',95,datetime('now'))")
    conn.execute("INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at) VALUES ('account-a','account-a:ted:a-1',1,'TED','new_high_match',95,datetime('now'))")
    a = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    device_id = conn.execute("SELECT id FROM push_devices WHERE installation_id='install-device-001'").fetchone()[0]
    register_push_device(conn, "account-b", "install-device-002", "ExpoPushToken[token-b]", "android")
    captured = []

    def post(_url, **kwargs):
        captured.extend(kwargs["json"])
        return _accepted()

    assert submit_pending_pushes(conn, "account-a", post=post) == 1
    assert len(captured) == 1
    assert captured[0]["to"] == "ExpoPushToken[token-a]"
    assert captured[0]["title"] == "Nova oportunidade ObraSignal"
    assert captured[0]["body"] == "Abre o ObraSignal para confirmar uma nova oportunidade."
    assert "Obra A confidencial" not in str(captured[0])
    assert captured[0]["data"] == {"opportunityId": 1, "eventId": 1, "bindingId": a["binding_id"]}
    assert submit_pending_pushes(conn, "account-a", post=post) == 0
    assert len(captured) == 1

    rotated = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a-rotated]", "android")
    assert rotated["binding_id"] != a["binding_id"]
    rotated_row = conn.execute("SELECT id,expo_push_token FROM push_devices WHERE installation_id='install-device-001'").fetchone()
    assert tuple(rotated_row) == (device_id, "ExpoPushToken[token-a-rotated]")
    # The accepted delivery ledger remains attached to the stable installation,
    # so token rotation cannot replay the same historical event.
    assert submit_pending_pushes(conn, "account-a", post=post) == 0
    assert len(captured) == 1

    delivery = conn.execute("SELECT ticket_id,submitted_at,attempt_count,last_attempt_at FROM push_deliveries").fetchone()
    assert delivery["ticket_id"] == "ticket-a"
    assert delivery["submitted_at"]
    assert delivery["attempt_count"] == 1
    assert delivery["last_attempt_at"]
    conn.close()


def test_transport_failure_is_observable_and_retryable_without_failing_event_truth():
    conn = _conn()
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (3,'TED','A-3','Obra C','2099-01-01',93,datetime('now'))")
    conn.execute("INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at) VALUES ('account-a','account-a:ted:a-3',3,'TED','new_high_match',93,datetime('now'))")
    register_push_device(conn, "account-a", "install-device-004", "ExpoPushToken[token-c]", "android")

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    assert submit_pending_pushes(conn, "account-a", post=unavailable) == 0
    failed = conn.execute("SELECT submitted_at,last_error,attempt_count,last_attempt_at FROM push_deliveries").fetchone()
    assert failed["submitted_at"] is None
    assert failed["last_error"] == "transport_RuntimeError"
    assert failed["attempt_count"] == 1
    assert failed["last_attempt_at"]
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is None

    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("ticket-retry")) == 1
    retried = conn.execute("SELECT ticket_id,submitted_at,last_error,attempt_count,last_attempt_at FROM push_deliveries").fetchone()
    assert retried["ticket_id"] == "ticket-retry"
    assert retried["submitted_at"]
    assert retried["last_error"] is None
    assert retried["attempt_count"] == 2
    assert retried["last_attempt_at"]
    conn.close()


def test_missing_provider_ticket_is_recorded_for_retry():
    conn = _conn()
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (4,'TED','A-4','Obra D','2099-01-01',92,datetime('now'))")
    conn.execute("INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at) VALUES ('account-a','account-a:ted:a-4',4,'TED','new_high_match',92,datetime('now'))")
    register_push_device(conn, "account-a", "install-device-005", "ExpoPushToken[token-d]", "android")

    class EmptyResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": []}

    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: EmptyResponse()) == 0
    failed = conn.execute("SELECT submitted_at,last_error,attempt_count,last_attempt_at FROM push_deliveries").fetchone()
    assert failed["submitted_at"] is None
    assert failed["last_error"] == "push_response_missing_ticket"
    assert failed["attempt_count"] == 1
    assert failed["last_attempt_at"]
    conn.close()


def test_device_not_registered_is_pruned_without_marking_event_delivered():
    conn = _conn()
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (2,'TED','A-2','Obra B','2099-01-01',91,datetime('now'))")
    conn.execute("INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at) VALUES ('account-a','account-a:ted:a-2',2,'TED','new_high_match',91,datetime('now'))")
    register_push_device(conn, "account-a", "install-device-003", "ExpoPushToken[dead-token]", "android")

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": [{"status": "error", "message": "not registered", "details": {"error": "DeviceNotRegistered"}}]}

    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: Response()) == 0
    assert conn.execute("SELECT COUNT(*) FROM push_devices").fetchone()[0] == 0
    attempt = conn.execute("SELECT last_error,attempt_count,last_attempt_at FROM push_deliveries").fetchone()
    assert attempt["last_error"] == "DeviceNotRegistered"
    assert attempt["attempt_count"] == 1
    assert attempt["last_attempt_at"]
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is None
    conn.close()
