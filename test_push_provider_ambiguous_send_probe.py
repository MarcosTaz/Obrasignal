"""Execution Factory failing-before for provider-accepted/local-ledger crash gap.

DO NOT MERGE / NOT NOTIFICATION OWNER REPAIR / NOT CANONICAL.
"""
import sqlite3

import notification_events as notifications


def _conn(path):
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
    conn.execute(
        "INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen) "
        "VALUES (1,'TED','ambiguous-1','Obra','2099-01-01',95,datetime('now'))"
    )
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a','account-a:ted:ambiguous-1',1,'TED','new_high_match',95,datetime('now'))"""
    )
    notifications.register_push_device(
        conn,
        "account-a",
        "install-ambiguous-001",
        "ExpoPushToken[ambiguous-token]",
        "android",
    )
    conn.commit()

    provider_calls = []

    def accepted_post(*args, **kwargs):
        provider_calls.append(kwargs.get("json"))
        return _accepted()

    original_record = notifications._record_push_attempt

    def crash_before_local_ledger(*args, **kwargs):
        # The provider has already returned an accepted ticket. Model abrupt
        # process death before the attempt/ticket can be durably recorded.
        raise SystemExit("synthetic process death after provider acceptance")

    monkeypatch.setattr(notifications, "_record_push_attempt", crash_before_local_ledger)
    try:
        notifications.submit_pending_pushes(conn, "account-a", post=accepted_post)
    except SystemExit:
        pass
    conn.close()

    # Restart with the normal local-ledger writer. Because no delivery attempt
    # became durable, current discovery sees the same event/device pair pending.
    monkeypatch.setattr(notifications, "_record_push_attempt", original_record)
    conn = _conn(db_path)
    notifications.submit_pending_pushes(conn, "account-a", post=accepted_post)
    conn.close()

    # Required zero-duplicate irreversible-side-effect invariant: an ambiguous
    # provider-accepted send must not cause a second logical provider submission.
    assert len(provider_calls) == 1
