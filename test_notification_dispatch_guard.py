"""Passing-after invariants for the provider-send/local-ledger crash boundary."""
import sqlite3
from pathlib import Path

import notification_events as notifications
import notification_dispatch_guard as guard


def _conn(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tenders(
            id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
            buyer TEXT, country TEXT, url TEXT, deadline TEXT, publication_date TEXT,
            score INTEGER, first_seen TEXT
        )"""
    )
    notifications.ensure_event_table(conn)
    return conn


def _seed(conn, external_id="ambiguous-1"):
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) "
        "VALUES (1,'TED',?,'Obra','2099-01-01',95,datetime('now'))",
        (external_id,),
    )
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a',?,1,'TED','new_high_match',95,datetime('now'))""",
        (f"account-a:ted:{external_id}",),
    )
    notifications.register_push_device(
        conn,
        "account-a",
        "install-ambiguous-001",
        "ExpoPushToken[ambiguous-token]",
        "android",
    )
    conn.commit()


def _accepted(ticket_id="ticket-accepted"):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"status": "ok", "id": ticket_id}]}

    return Response()


def test_provider_accept_before_local_attempt_persistence_is_not_replayed(monkeypatch, tmp_path):
    db_path = tmp_path / "ambiguous-send.sqlite"
    conn = _conn(db_path)
    _seed(conn)
    provider_calls = []

    def accepted_post(*args, **kwargs):
        provider_calls.append(kwargs.get("json"))
        return _accepted()

    original_record = notifications._record_push_attempt

    def crash_before_local_ledger(*args, **kwargs):
        raise SystemExit("synthetic process death after provider acceptance")

    monkeypatch.setattr(notifications, "_record_push_attempt", crash_before_local_ledger)
    try:
        guard.submit_pending_pushes(conn, "account-a", post=accepted_post)
    except SystemExit:
        pass
    conn.close()

    # The durable pre-dispatch marker survived. A fresh process cannot know
    # whether the external side effect occurred, so it must fail closed instead
    # of replaying the same event/device pair automatically.
    monkeypatch.setattr(notifications, "_record_push_attempt", original_record)
    conn = _conn(db_path)
    assert guard.submit_pending_pushes(conn, "account-a", post=accepted_post) == 0
    row = conn.execute(
        "SELECT attempt_count,last_error,next_attempt_at,failed_at,submitted_at "
        "FROM push_deliveries"
    ).fetchone()
    conn.close()

    assert len(provider_calls) == 1
    assert row["attempt_count"] == 1
    assert row["last_error"] == guard.AMBIGUOUS_PROVIDER_STATE
    assert row["next_attempt_at"] is None
    assert row["failed_at"] is not None
    assert row["submitted_at"] is None


def test_normal_provider_acceptance_preserves_existing_ticket_truth():
    conn = _conn()
    _seed(conn, external_id="normal-accepted")
    calls = []

    def provider(*args, **kwargs):
        calls.append(kwargs.get("json"))
        return _accepted("ticket-normal")

    assert guard.submit_pending_pushes(conn, "account-a", post=provider) == 1
    row = conn.execute(
        "SELECT attempt_count,ticket_id,submitted_at,last_error,failed_at FROM push_deliveries"
    ).fetchone()
    conn.close()

    assert len(calls) == 1
    assert row["attempt_count"] == 1
    assert row["ticket_id"] == "ticket-normal"
    assert row["submitted_at"] is not None
    assert row["last_error"] is None
    assert row["failed_at"] is None


def test_explicit_transport_failure_keeps_existing_bounded_retry_policy():
    conn = _conn()
    _seed(conn, external_id="transport-retry")
    calls = []

    def provider(*args, **kwargs):
        calls.append(kwargs.get("json"))
        raise RuntimeError("synthetic transport failure")

    assert guard.submit_pending_pushes(conn, "account-a", post=provider) == 0
    row = conn.execute(
        "SELECT attempt_count,last_error,next_attempt_at,failed_at FROM push_deliveries"
    ).fetchone()
    conn.close()

    assert len(calls) == 1
    assert row["attempt_count"] == 1
    assert row["last_error"] == "transport_RuntimeError"
    assert row["next_attempt_at"] is not None
    assert row["failed_at"] is None


def test_production_entrypoint_installs_guard_before_worker_start():
    root = Path(__file__).resolve().parent
    source = (root / "cors_app.py").read_text(encoding="utf-8")
    assert "install_notification_dispatch_guard()" in source
    assert source.index("install_notification_dispatch_guard()") < source.index("start_background_worker()")
