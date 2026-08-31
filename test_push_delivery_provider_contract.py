"""Adversarial provider-contract regressions for remote push submission."""
import sqlite3

from notification_events import ensure_event_table, register_push_device, submit_pending_pushes


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


def test_ok_without_ticket_id_is_not_false_submitted_and_is_backed_off():
    conn = _conn()
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) VALUES (10,'TED','A-10','Obra A-10','2099-01-01',95,datetime('now'))"
    )
    conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
           VALUES ('account-a','account-a:ted:a-10',10,'TED','new_high_match',95,datetime('now'))"""
    )
    register_push_device(conn, "account-a", "install-device-010", "ExpoPushToken[token-ten]", "android")

    class MissingTicketIdResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"status": "ok"}]}

    assert submit_pending_pushes(
        conn,
        "account-a",
        post=lambda *_args, **_kwargs: MissingTicketIdResponse(),
    ) == 0

    delivery = conn.execute(
        """SELECT ticket_id,submitted_at,last_error,attempt_count,last_attempt_at,
                  next_attempt_at,failed_at
           FROM push_deliveries"""
    ).fetchone()
    assert delivery["ticket_id"] is None
    assert delivery["submitted_at"] is None
    assert delivery["last_error"] == "push_response_missing_ticket"
    assert delivery["attempt_count"] == 1
    assert delivery["last_attempt_at"]
    assert delivery["next_attempt_at"]
    assert delivery["failed_at"] is None

    # A malformed provider acknowledgement must not create a tight retry loop.
    assert submit_pending_pushes(
        conn,
        "account-a",
        post=lambda *_args, **_kwargs: MissingTicketIdResponse(),
    ) == 0
    assert conn.execute("SELECT attempt_count FROM push_deliveries").fetchone()[0] == 1
    conn.close()
