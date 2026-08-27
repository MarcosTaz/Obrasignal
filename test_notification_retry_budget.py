import sqlite3

from notification_events import (
    MAX_PUSH_ATTEMPTS,
    ensure_event_table,
    register_push_device,
    submit_pending_pushes,
)


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


def _seed_due(conn, *, attempt_count):
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) "
        "VALUES (435,'TED','RETRY-435','Retry budget','2099-01-01',95,datetime('now'))"
    )
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a','account-a:ted:retry-435',435,'TED','new_high_match',95,datetime('now'))"""
    )
    register_push_device(
        conn,
        "account-a",
        "install-retry-budget-435",
        "ExpoPushToken[retry-budget-435]",
        "android",
    )
    event_id = conn.execute("SELECT id FROM opportunity_events").fetchone()[0]
    device_id = conn.execute("SELECT id FROM push_devices").fetchone()[0]
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,attempt_count,last_error,last_attempt_at,
               next_attempt_at,expo_push_token,failed_at,submitted_at
           ) VALUES (?,?,?,?,?,?,?,?,NULL)""",
        (
            event_id,
            device_id,
            attempt_count,
            "transport_RuntimeError",
            "2000-01-01T00:00:00+00:00",
            "2000-01-01T00:00:00+00:00",
            "ExpoPushToken[retry-budget-435]",
            None,
        ),
    )
    conn.commit()


def test_extreme_legacy_attempt_count_is_terminalized_without_provider_replay():
    conn = _conn()
    _seed_due(conn, attempt_count=1_000_000)
    calls = []

    def provider(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("exhausted delivery must not reach provider")

    before = conn.execute("SELECT attempt_count FROM push_deliveries").fetchone()[0]
    assert submit_pending_pushes(conn, "account-a", post=provider) == 0
    after = conn.execute(
        "SELECT attempt_count,next_attempt_at,failed_at FROM push_deliveries"
    ).fetchone()
    assert calls == []
    assert after["attempt_count"] == before
    assert after["next_attempt_at"] is None
    assert after["failed_at"] is not None
    conn.close()


def test_eighth_failed_send_is_last_attempt_and_ninth_is_never_replayed():
    assert MAX_PUSH_ATTEMPTS == 8
    conn = _conn()
    _seed_due(conn, attempt_count=MAX_PUSH_ATTEMPTS - 1)
    calls = []

    class MissingTicket:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": []}

    def provider(*_args, **_kwargs):
        calls.append("called")
        return MissingTicket()

    assert submit_pending_pushes(conn, "account-a", post=provider) == 0
    terminal = conn.execute(
        "SELECT attempt_count,next_attempt_at,failed_at,last_error FROM push_deliveries"
    ).fetchone()
    assert calls == ["called"]
    assert terminal["attempt_count"] == MAX_PUSH_ATTEMPTS
    assert terminal["next_attempt_at"] is None
    assert terminal["failed_at"] is not None
    assert terminal["last_error"] == "push_response_missing_ticket"

    assert submit_pending_pushes(conn, "account-a", post=provider) == 0
    after = conn.execute("SELECT attempt_count FROM push_deliveries").fetchone()[0]
    assert calls == ["called"]
    assert after == MAX_PUSH_ATTEMPTS
    conn.close()
