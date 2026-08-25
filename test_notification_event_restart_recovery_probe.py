"""Execution failing-before: durable eligible notification work must survive restart.

This probe deliberately models the boundary where tender + account decision are
already durable, the process exits before opportunity_events is created, and the
worker resumes after the current two-minute discovery window. A correct
execution contract must rediscover the missing logical event rather than lose it
because wall-clock time elapsed.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

from decision_log import record_decision
from notification_events import ensure_event_table, record_new_opportunities


def _open(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def test_missing_event_is_rediscovered_after_process_restart(tmp_path):
    db_path = tmp_path / "notification-restart.db"

    # Phase 1: canonical opportunity/decision become durable, then the process
    # dies before the derived notification event is recorded.
    conn = _open(db_path)
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
        country TEXT, url TEXT, deadline TEXT, profile_reason TEXT,
        profile_score INTEGER, score INTEGER, first_seen TEXT
    )""")
    ensure_event_table(conn)
    old_first_seen = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute("""INSERT INTO tenders
        (id, source, external_id, title, country, url, deadline,
         profile_reason, profile_score, score, first_seen)
        VALUES (1,'TED','2026/S-restart','Pavilhão industrial','ES',
                'https://example.invalid/restart','2099-01-01','perfil: pavilhões',
                94,94,?)""", (old_first_seen,))
    record_decision(
        conn,
        "TED",
        "2026/S-restart",
        "QUALIFIED",
        "account-specific high match",
        score=94,
        account_id="default",
    )
    conn.commit()
    conn.close()

    # Phase 2: a fresh process/connection resumes. The logical event is absent
    # and still required. Wall-clock age alone must not make it undiscoverable.
    conn = _open(db_path)
    recovered = record_new_opportunities(conn, account_id="default", min_score=75)
    stored = conn.execute(
        "SELECT event_key, account_id, tender_id FROM opportunity_events WHERE tender_id=1"
    ).fetchall()
    conn.close()

    assert len(recovered) == 1
    assert len(stored) == 1
    assert stored[0]["account_id"] == "default"
    assert stored[0]["tender_id"] == 1
