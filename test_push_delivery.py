"""Regression coverage for account-scoped remote notification delivery."""
import sqlite3

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


def test_device_rebind_moves_installation_from_account_a_to_b():
    conn = _conn()
    first = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    again = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    assert again["binding_id"] == first["binding_id"]

    second = register_push_device(conn, "account-b", "install-device-001", "ExpoPushToken[token-a]", "android")
    assert second["binding_id"] != first["binding_id"]
    rows = conn.execute("SELECT account_id,installation_id,expo_push_token FROM push_devices").fetchall()
    assert [tuple(row) for row in rows] == [("account-b", "install-device-001", "ExpoPushToken[token-a]")]
    conn.close()


def test_push_submission_is_account_scoped_idempotent_and_tray_safe():
    conn = _conn()
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (1,'TED','A-1','Obra A confidencial','2099-01-01',95,datetime('now'))")
    conn.execute("INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at) VALUES ('account-a','account-a:ted:a-1',1,'TED','new_high_match',95,datetime('now'))")
    a = register_push_device(conn, "account-a", "install-device-001", "ExpoPushToken[token-a]", "android")
    register_push_device(conn, "account-b", "install-device-002", "ExpoPushToken[token-b]", "android")
    captured = []

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": [{"status": "ok", "id": "ticket-a"}]}

    def post(_url, **kwargs):
        captured.extend(kwargs["json"])
        return Response()

    assert submit_pending_pushes(conn, "account-a", post=post) == 1
    assert len(captured) == 1
    assert captured[0]["to"] == "ExpoPushToken[token-a]"
    assert captured[0]["title"] == "Nova oportunidade ObraSignal"
    assert captured[0]["body"] == "Abre o ObraSignal para confirmar uma nova oportunidade."
    assert "Obra A confidencial" not in str(captured[0])
    assert captured[0]["data"] == {"opportunityId": 1, "eventId": 1, "bindingId": a["binding_id"]}
    assert submit_pending_pushes(conn, "account-a", post=post) == 0
    assert len(captured) == 1
    delivery = conn.execute("SELECT ticket_id,submitted_at FROM push_deliveries").fetchone()
    assert delivery["ticket_id"] == "ticket-a"
    assert delivery["submitted_at"]
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
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is None
    conn.close()
