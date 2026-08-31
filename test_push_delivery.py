"""Regression coverage for account-scoped remote notification delivery."""
import sqlite3

from app import APP
from notification_events import (
    ensure_event_table,
    reconcile_push_receipts,
    register_push_device,
    submit_pending_pushes,
    unregister_push_device,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
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


def _event(conn, tender_id, suffix, score=95):
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (?,?,?,?,?,?,datetime('now'))",
        (tender_id, "TED", suffix, f"Obra {suffix}", "2099-01-01", score),
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES ('account-a',?,?, 'TED','new_high_match',?,datetime('now'))""",
        (f"account-a:ted:{suffix.lower()}", tender_id, score),
    )


def test_device_rebind_moves_installation_from_account_a_to_b_without_changing_device_identity():
    conn = _conn()
    first = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    first_id = conn.execute("SELECT id FROM push_devices WHERE installation_id='install-device-001'").fetchone()[0]
    again = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    assert again["binding_id"] == first["binding_id"]

    second = register_push_device(conn, "account-b", "install-device-001", "ExpoPushToken[token-a]", "android")
    assert second["binding_id"] != first["binding_id"]
    rows = conn.execute("SELECT id,account_id,installation_id,expo_push_token,revoked_at FROM push_devices").fetchall()
    assert [tuple(row) for row in rows] == [(first_id, "account-b", "install-device-001", "ExpoPushToken[token-a]", None)]
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
        row = conn.execute("SELECT account_id,revoked_at FROM push_devices").fetchone()
        assert tuple(row) == ("account-a", None)
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


def test_unregister_then_reenable_preserves_dedupe_identity_and_removes_usable_token():
    conn = _conn()
    _event(conn, 6, "A-6")
    register_push_device(conn, "account-a", "install-device-006", "ExpoPushToken[token-six]", "android")
    device_id = conn.execute("SELECT id FROM push_devices WHERE installation_id='install-device-006'").fetchone()[0]
    captured = []

    def post(_url, **kwargs):
        captured.extend(kwargs["json"])
        return _accepted("ticket-six")

    assert submit_pending_pushes(conn, "account-a", post=post) == 1
    assert unregister_push_device(conn, "account-a", "install-device-006") is True
    revoked = conn.execute("SELECT id,expo_push_token,revoked_at FROM push_devices WHERE installation_id='install-device-006'").fetchone()
    assert revoked["id"] == device_id
    assert revoked["expo_push_token"].startswith("revoked:")
    assert revoked["revoked_at"]
    assert submit_pending_pushes(conn, "account-a", post=post) == 0

    register_push_device(conn, "account-a", "install-device-006", "ExpoPushToken[token-six-new]", "android")
    reenabled = conn.execute("SELECT id,expo_push_token,revoked_at FROM push_devices WHERE installation_id='install-device-006'").fetchone()
    assert tuple(reenabled) == (device_id, "ExpoPushToken[token-six-new]", None)
    assert submit_pending_pushes(conn, "account-a", post=post) == 0
    assert len(captured) == 1
    conn.close()


def test_transport_failure_is_observable_backed_off_and_retryable_without_failing_event_truth():
    conn = _conn()
    _event(conn, 3, "A-3", 93)
    register_push_device(conn, "account-a", "install-device-004", "ExpoPushToken[token-c]", "android")

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    assert submit_pending_pushes(conn, "account-a", post=unavailable) == 0
    failed = conn.execute("SELECT submitted_at,last_error,attempt_count,last_attempt_at,next_attempt_at FROM push_deliveries").fetchone()
    assert failed["submitted_at"] is None
    assert failed["last_error"] == "transport_RuntimeError"
    assert failed["attempt_count"] == 1
    assert failed["last_attempt_at"]
    assert failed["next_attempt_at"]
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is None

    # Immediate retries are suppressed; once due, the same event/device pair is retried.
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("too-early")) == 0
    conn.execute("UPDATE push_deliveries SET next_attempt_at='2000-01-01T00:00:00+00:00'")
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("ticket-retry")) == 1
    retried = conn.execute("SELECT ticket_id,submitted_at,last_error,attempt_count,last_attempt_at,next_attempt_at FROM push_deliveries").fetchone()
    assert retried["ticket_id"] == "ticket-retry"
    assert retried["submitted_at"]
    assert retried["last_error"] is None
    assert retried["attempt_count"] == 2
    assert retried["last_attempt_at"]
    assert retried["next_attempt_at"] is None
    conn.close()


def test_missing_provider_ticket_is_observable_and_backed_off_for_retry():
    conn = _conn()
    _event(conn, 4, "A-4", 92)
    register_push_device(conn, "account-a", "install-device-005", "ExpoPushToken[token-d]", "android")

    class EmptyResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": []}

    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: EmptyResponse()) == 0
    failed = conn.execute("SELECT submitted_at,last_error,attempt_count,last_attempt_at,next_attempt_at FROM push_deliveries").fetchone()
    assert failed["submitted_at"] is None
    assert failed["last_error"] == "push_response_missing_ticket"
    assert failed["attempt_count"] == 1
    assert failed["last_attempt_at"]
    assert failed["next_attempt_at"]
    conn.close()


def test_device_not_registered_revokes_usable_token_without_marking_event_delivered():
    conn = _conn()
    _event(conn, 2, "A-2", 91)
    register_push_device(conn, "account-a", "install-device-003", "ExpoPushToken[dead-token]", "android")

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": [{"status": "error", "message": "not registered", "details": {"error": "DeviceNotRegistered"}}]}

    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: Response()) == 0
    device = conn.execute("SELECT expo_push_token,revoked_at,last_error FROM push_devices").fetchone()
    assert device["expo_push_token"].startswith("revoked:")
    assert device["revoked_at"]
    assert device["last_error"] == "DeviceNotRegistered"
    attempt = conn.execute("SELECT last_error,attempt_count,last_attempt_at,failed_at FROM push_deliveries").fetchone()
    assert attempt["last_error"] == "DeviceNotRegistered"
    assert attempt["attempt_count"] == 1
    assert attempt["last_attempt_at"]
    assert attempt["failed_at"]
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is None
    conn.close()


def test_receipt_ok_records_provider_acceptance_not_user_delivery():
    conn = _conn()
    _event(conn, 7, "A-7")
    register_push_device(conn, "account-a", "install-device-007", "ExpoPushToken[token-seven]", "android")
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("ticket-seven")) == 1

    captured = []
    def receipts(_url, **kwargs):
        captured.append(kwargs["json"])
        return _receipt({"ticket-seven": {"status": "ok"}})

    assert reconcile_push_receipts(conn, "account-a", min_age_seconds=0, post=receipts) == 1
    assert captured == [{"ids": ["ticket-seven"]}]
    delivery = conn.execute("SELECT receipt_status,receipt_checked_at,receipt_error FROM push_deliveries").fetchone()
    assert tuple(delivery)[:1] == ("provider_accepted",)
    assert delivery["receipt_checked_at"]
    assert delivery["receipt_error"] is None
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is None
    conn.close()


def test_delayed_device_not_registered_receipt_cannot_revoke_a_rotated_token():
    conn = _conn()
    _event(conn, 8, "A-8")
    register_push_device(conn, "account-a", "install-device-008", "ExpoPushToken[token-eight-old]", "android")
    device_id = conn.execute("SELECT id FROM push_devices").fetchone()[0]
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("ticket-eight")) == 1

    register_push_device(conn, "account-a", "install-device-008", "ExpoPushToken[token-eight-new]", "android")
    assert reconcile_push_receipts(
        conn,
        "account-a",
        min_age_seconds=0,
        post=lambda *_args, **_kwargs: _receipt({
            "ticket-eight": {
                "status": "error",
                "message": "not registered",
                "details": {"error": "DeviceNotRegistered"},
            }
        }),
    ) == 1
    current = conn.execute("SELECT id,expo_push_token,revoked_at FROM push_devices").fetchone()
    assert tuple(current) == (device_id, "ExpoPushToken[token-eight-new]", None)
    delivery = conn.execute("SELECT receipt_status,receipt_error,failed_at FROM push_deliveries").fetchone()
    assert delivery["receipt_status"] == "error"
    assert delivery["receipt_error"] == "DeviceNotRegistered"
    assert delivery["failed_at"]
    conn.close()


def test_message_rate_exceeded_receipt_schedules_bounded_resubmission():
    conn = _conn()
    _event(conn, 9, "A-9")
    register_push_device(conn, "account-a", "install-device-009", "ExpoPushToken[token-nine]", "android")
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("ticket-nine")) == 1

    assert reconcile_push_receipts(
        conn,
        "account-a",
        min_age_seconds=0,
        post=lambda *_args, **_kwargs: _receipt({
            "ticket-nine": {
                "status": "error",
                "message": "rate exceeded",
                "details": {"error": "MessageRateExceeded"},
            }
        }),
    ) == 1
    delivery = conn.execute("SELECT ticket_id,submitted_at,last_error,next_attempt_at,receipt_status,failed_at FROM push_deliveries").fetchone()
    assert delivery["ticket_id"] is None
    assert delivery["submitted_at"] is None
    assert delivery["last_error"] == "MessageRateExceeded"
    assert delivery["next_attempt_at"]
    assert delivery["receipt_status"] is None
    assert delivery["failed_at"] is None
    assert submit_pending_pushes(conn, "account-a", post=lambda *_args, **_kwargs: _accepted("too-early")) == 0
    conn.close()


def test_account_bootstrap_events_dispatch_through_the_same_canonical_sender(monkeypatch):
    import notification_events
    from account_onboarding import _emit_bootstrap_events
    from decision_log import record_decision
    from opportunity_match_pipeline import RULE_VERSION

    conn = _conn()
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline,publication_date,score,first_seen) VALUES (5,'TED','A-5','Obra E','2099-01-01','2026-08-25',96,datetime('now'))")
    record_decision(
        conn,
        "TED",
        "A-5",
        "QUALIFIED",
        "current fixture",
        score=96,
        rule_version=RULE_VERSION,
        account_id="account-a",
    )
    calls = []

    def dispatch(dispatch_conn, account_id, **_kwargs):
        assert dispatch_conn is conn
        calls.append(account_id)
        return 0

    monkeypatch.setattr(notification_events, "submit_pending_pushes", dispatch)
    assert _emit_bootstrap_events(conn, "account-a") == 1
    assert calls == ["account-a"]
    event = conn.execute("SELECT account_id,event_key,tender_id FROM opportunity_events").fetchone()
    assert tuple(event) == ("account-a", "account-a:TED:A-5", 5)
    conn.close()
