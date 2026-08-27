"""Passing-after acceptance for exact Expo ticket -> local delivery parentage."""
import sqlite3

import notification_events as notifications


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    notifications.ensure_event_table(conn)
    return conn


def _event(conn, tender_id, key, score=90):
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES (?,?,?,?,?,?,?)""",
        ("account-a", f"account-a:ted:{key}", tender_id, "TED", "new_high_match", score, "2000-01-01T00:00:00+00:00"),
    )
    return conn.execute("SELECT id FROM opportunity_events WHERE event_key=?", (f"account-a:ted:{key}",)).fetchone()["id"]


def _device(conn, suffix):
    notifications.register_push_device(
        conn,
        "account-a",
        f"install-{suffix}",
        f"ExpoPushToken[{suffix}]",
        "android",
    )
    return conn.execute("SELECT id,expo_push_token FROM push_devices WHERE installation_id=?", (f"install-{suffix}",)).fetchone()


def _receipt_response(ticket_id, status="ok"):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {ticket_id: {"status": status}}}

    return Response()


def test_duplicate_historical_ticket_never_fans_one_receipt_into_two_local_parents():
    conn = _conn()
    events = [_event(conn, 101, "ticket-a", 90), _event(conn, 102, "ticket-b", 91)]
    devices = [_device(conn, "ticket-parent-a"), _device(conn, "ticket-parent-b")]
    duplicate_ticket = "provider-ticket-shared"
    now = "2000-01-01T00:00:00+00:00"
    for event_id, device in zip(events, devices):
        conn.execute(
            """INSERT INTO push_deliveries(
                   event_id,push_device_id,ticket_id,submitted_at,attempt_count,last_attempt_at,expo_push_token
               ) VALUES (?,?,?,?,1,?,?)""",
            (event_id, device["id"], duplicate_ticket, now, now, device["expo_push_token"]),
        )
    conn.commit()

    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _receipt_response(duplicate_ticket)

    reconciled = notifications.reconcile_push_receipts(
        conn, "account-a", min_age_seconds=0, post=post
    )
    rows = conn.execute(
        "SELECT receipt_status,receipt_error,failed_at,ticket_id FROM push_deliveries ORDER BY id"
    ).fetchall()
    claims = conn.execute("SELECT * FROM push_ticket_parents").fetchall()

    assert reconciled == 0
    assert calls == [], "ambiguous provider ticket must fail closed before receipt lookup"
    assert len(rows) == 2
    assert all(row["ticket_id"] == duplicate_ticket for row in rows), "retain ambiguous evidence for audit"
    assert all(row["receipt_status"] == "error" for row in rows)
    assert all(row["receipt_error"] == "provider_ticket_parentage_conflict" for row in rows)
    assert all(row["failed_at"] for row in rows)
    assert claims == []
    conn.close()


def test_unique_historical_ticket_is_safely_backfilled_and_reconciled_to_exact_parent():
    conn = _conn()
    event_id = _event(conn, 201, "unique-ticket", 93)
    device = _device(conn, "unique-parent")
    ticket_id = "provider-ticket-unique"
    now = "2000-01-01T00:00:00+00:00"
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,last_attempt_at,expo_push_token
           ) VALUES (?,?,?,?,1,?,?)""",
        (event_id, device["id"], ticket_id, now, now, device["expo_push_token"]),
    )
    delivery_id = conn.execute("SELECT id FROM push_deliveries").fetchone()["id"]
    conn.commit()

    reconciled = notifications.reconcile_push_receipts(
        conn,
        "account-a",
        min_age_seconds=0,
        post=lambda *_args, **_kwargs: _receipt_response(ticket_id),
    )
    delivery = conn.execute("SELECT * FROM push_deliveries WHERE id=?", (delivery_id,)).fetchone()
    claim = conn.execute("SELECT * FROM push_ticket_parents WHERE ticket_id=?", (ticket_id,)).fetchone()

    assert reconciled == 1
    assert delivery["receipt_status"] == "provider_accepted"
    assert delivery["receipt_error"] is None
    assert claim is not None
    assert claim["push_delivery_id"] == delivery_id
    conn.close()


def test_duplicate_ticket_ids_returned_by_provider_are_persisted_but_never_authoritative_or_retried():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            deadline TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,deadline) VALUES (1,'TED','SEND-DUP','2099-01-01')"
    )
    notifications.ensure_event_table(conn)
    event_id = _event(conn, 1, "send-dup", 95)
    _device(conn, "send-parent-a")
    _device(conn, "send-parent-b")
    conn.commit()
    duplicate_ticket = "provider-ticket-duplicate-response"

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"status": "ok", "id": duplicate_ticket},
                    {"status": "ok", "id": duplicate_ticket},
                ]
            }

    submitted = notifications.submit_pending_pushes(
        conn, "account-a", post=lambda *_args, **_kwargs: Response()
    )
    rows = conn.execute(
        """SELECT event_id,ticket_id,receipt_status,receipt_error,failed_at,next_attempt_at
           FROM push_deliveries ORDER BY id"""
    ).fetchall()
    claims = conn.execute("SELECT * FROM push_ticket_parents").fetchall()

    assert submitted == 0
    assert len(rows) == 2
    assert all(row["event_id"] == event_id for row in rows)
    assert all(row["ticket_id"] == duplicate_ticket for row in rows)
    assert all(row["receipt_status"] == "error" for row in rows)
    assert all(row["receipt_error"] == "provider_ticket_parentage_conflict" for row in rows)
    assert all(row["failed_at"] for row in rows)
    assert all(row["next_attempt_at"] is None for row in rows), "ambiguous accepted sends must not be replayed"
    assert claims == []
    conn.close()
