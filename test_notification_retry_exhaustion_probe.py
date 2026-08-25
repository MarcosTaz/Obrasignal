"""Resilience failing-before probe for Notification Delivery retry exhaustion.

Diagnostic only.  The numeric value here is intentionally absurdly above any
credible finite provider retry budget; the Notification owner still owns the
actual budget and terminal-state design.  The probe asks only one question:
can an already-enormously-retried delivery remain eligible forever?
"""

import sqlite3

from notification_events import ensure_event_table, register_push_device, submit_pending_pushes


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
            buyer TEXT, country TEXT, url TEXT, deadline TEXT, publication_date TEXT,
            score INTEGER, first_seen TEXT
        )"""
    )
    ensure_event_table(conn)
    return conn


def test_due_delivery_with_extreme_attempt_count_is_not_replayed_forever():
    conn = _conn()
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) "
        "VALUES (435,'TED','RETRY-435','Retry exhaustion probe','2099-01-01',95,datetime('now'))"
    )
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES (
               'account-a','account-a:ted:retry-435',435,'TED','new_high_match',95,datetime('now')
           )"""
    )
    register_push_device(
        conn,
        "account-a",
        "install-retry-probe-435",
        "ExpoPushToken[retry-probe-435]",
        "android",
    )
    device_id = conn.execute("SELECT id FROM push_devices").fetchone()[0]
    event_id = conn.execute("SELECT id FROM opportunity_events").fetchone()[0]
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,attempt_count,last_error,last_attempt_at,
               next_attempt_at,expo_push_token,failed_at,submitted_at
           ) VALUES (?,?,?,?,?,?,?,?,NULL)""",
        (
            event_id,
            device_id,
            1_000_000,
            "transport_RuntimeError",
            "2000-01-01T00:00:00+00:00",
            "2000-01-01T00:00:00+00:00",
            "ExpoPushToken[retry-probe-435]",
            None,
        ),
    )
    conn.commit()

    calls = []

    class MissingTicket:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": []}

    def provider(*_args, **_kwargs):
        calls.append("called")
        return MissingTicket()

    before = conn.execute(
        "SELECT attempt_count,next_attempt_at,failed_at FROM push_deliveries"
    ).fetchone()
    assert before["attempt_count"] == 1_000_000

    assert submit_pending_pushes(conn, "account-a", post=provider) == 0

    after = conn.execute(
        "SELECT attempt_count,next_attempt_at,failed_at FROM push_deliveries"
    ).fetchone()

    # Failing-before on #329@d8b14d56: current pending selection has no attempt
    # ceiling, so it calls the provider and increments to 1,000,001.  A repaired
    # owner contract must make this delivery non-pending before the provider call.
    assert calls == []
    assert after["attempt_count"] == before["attempt_count"]
    conn.close()
