"""Data Lineage revalidation: exact decision parentage does not imply provider-ticket parentage.

DRAFT / DO NOT MERGE / NOT NOTIFICATION OWNER REPAIR / NOT CANONICAL.
Synthetic SQLite + fake provider only; no network/provider/customer data.
"""
import sqlite3

import notification_events as notifications


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    notifications.ensure_event_table(conn)
    return conn


def _receipt_response(ticket_id):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {ticket_id: {"status": "ok"}}}

    return Response()


def test_one_provider_ticket_cannot_authorize_two_local_deliveries_after_decision_parent_repair():
    conn = _conn()
    now = "2000-01-01T00:00:00+00:00"

    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a','account-a:ted:ticket-a',101,'TED','new_high_match',90,?)""",
        (now,),
    )
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a','account-a:ted:ticket-b',102,'TED','new_high_match',91,?)""",
        (now,),
    )

    notifications.register_push_device(
        conn,
        "account-a",
        "install-ticket-parent-a",
        "ExpoPushToken[ticket-parent-a]",
        "android",
    )
    notifications.register_push_device(
        conn,
        "account-a",
        "install-ticket-parent-b",
        "ExpoPushToken[ticket-parent-b]",
        "android",
    )

    events = conn.execute("SELECT id FROM opportunity_events ORDER BY id").fetchall()
    devices = conn.execute("SELECT id,expo_push_token FROM push_devices ORDER BY id").fetchall()
    duplicate_ticket = "provider-ticket-shared"

    for event, device in zip(events, devices):
        conn.execute(
            """INSERT INTO push_deliveries(
                   event_id,push_device_id,ticket_id,submitted_at,attempt_count,
                   last_attempt_at,expo_push_token
               ) VALUES (?,?,?,?,1,?,?)""",
            (
                event["id"],
                device["id"],
                duplicate_ticket,
                now,
                now,
                device["expo_push_token"],
            ),
        )
    conn.commit()

    rows = conn.execute(
        "SELECT id,event_id,push_device_id,ticket_id FROM push_deliveries ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["event_id"] != rows[1]["event_id"]
    assert rows[0]["push_device_id"] != rows[1]["push_device_id"]
    assert rows[0]["ticket_id"] == rows[1]["ticket_id"] == duplicate_ticket

    notifications.reconcile_push_receipts(
        conn,
        "account-a",
        min_age_seconds=0,
        post=lambda *_args, **_kwargs: _receipt_response(duplicate_ticket),
    )

    accepted = conn.execute(
        """SELECT event_id,push_device_id,ticket_id,receipt_status
           FROM push_deliveries
           WHERE receipt_status='provider_accepted'
           ORDER BY id"""
    ).fetchall()

    assert len(accepted) <= 1
    conn.close()
