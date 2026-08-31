"""Tests for the mobile alert feed contract."""
import sqlite3
from datetime import datetime, timedelta, timezone

from account_onboarding import _emit_bootstrap_events
from decision_log import record_decision
from notification_events import ensure_event_table, record_new_opportunities


def _conn_with_tender(global_score=94, first_seen=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
        country TEXT, url TEXT, deadline TEXT, publication_date TEXT,
        profile_reason TEXT, profile_score INTEGER, score INTEGER, first_seen TEXT
    )""")
    recent = first_seen or (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    conn.execute("""INSERT INTO tenders
        (id, source, external_id, title, country, url, deadline, publication_date,
         profile_reason, profile_score, score, first_seen)
        VALUES (1,'TED','2026/S-1','Pavilhão industrial','ES',
                'https://example.invalid/1','2099-01-01','2026-08-31','perfil: pavilhões',
                ?,?,?)""", (global_score, global_score, recent))
    ensure_event_table(conn)
    return conn


def _qualify(conn, account='default', score=94):
    record_decision(
        conn, 'TED', '2026/S-1', 'QUALIFIED', 'strong tenant match',
        score=score, account_id=account,
    )


def test_event_feed_is_idempotent_and_has_delivery_state():
    conn = _conn_with_tender()
    _qualify(conn)
    first = record_new_opportunities(conn, min_score=75)
    second = record_new_opportunities(conn, min_score=75)
    assert len(first) == 1
    assert first[0]['score'] == 94
    assert len(second) == 0
    event = conn.execute("SELECT delivered_at FROM opportunity_events WHERE tender_id=1").fetchone()
    assert event[0] is None
    conn.execute("UPDATE opportunity_events SET delivered_at='2026-08-18T17:01:00+00:00' WHERE tender_id=1")
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE tender_id=1").fetchone()[0] is not None
    conn.close()


def test_high_global_score_never_alerts_a_tenant_that_rejected_the_opportunity():
    conn = _conn_with_tender(global_score=99)
    record_decision(
        conn, 'TED', '2026/S-1', 'QUALIFIED', 'tenant A matches',
        score=91, account_id='tenant-a',
    )
    record_decision(
        conn, 'TED', '2026/S-1', 'REJECT', 'tenant B has hard blockers',
        score=35, account_id='tenant-b',
    )

    events_a = record_new_opportunities(conn, account_id='tenant-a', min_score=75)
    events_b = record_new_opportunities(conn, account_id='tenant-b', min_score=75)

    assert len(events_a) == 1
    assert events_a[0]['score'] == 91
    assert events_b == []
    rows = conn.execute("SELECT account_id,score FROM opportunity_events ORDER BY account_id").fetchall()
    assert [(row['account_id'], row['score']) for row in rows] == [('tenant-a', 91)]
    conn.close()


def test_review_decision_below_alert_boundary_does_not_emit_push_event():
    conn = _conn_with_tender(global_score=99)
    record_decision(
        conn, 'TED', '2026/S-1', 'REVIEW', 'needs customer review',
        score=74, account_id='tenant-a',
    )
    assert record_new_opportunities(conn, account_id='tenant-a', min_score=75) == []
    conn.close()


def test_stale_same_day_iso_timestamp_is_not_misclassified_as_new_without_sync_truth():
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    conn = _conn_with_tender(global_score=99, first_seen=stale)
    _qualify(conn, account='tenant-a', score=93)
    assert record_new_opportunities(conn, account_id='tenant-a', min_score=75) == []
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0] == 0
    conn.close()


def test_latest_sync_truth_survives_processing_longer_than_two_minutes():
    sync_finished = (datetime.now(timezone.utc) - timedelta(minutes=7)).isoformat()
    conn = _conn_with_tender(global_score=99, first_seen=sync_finished)
    conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
    conn.execute("INSERT INTO sync_runs VALUES(1,?)", (sync_finished,))
    _qualify(conn, account='tenant-a', score=93)
    events = record_new_opportunities(conn, account_id='tenant-a', min_score=75)
    assert len(events) == 1
    assert events[0]['score'] == 93
    conn.close()


def test_bootstrap_event_and_regular_sync_event_are_the_same_identity():
    conn = _conn_with_tender(global_score=99)
    _qualify(conn, account='tenant-a', score=92)
    assert _emit_bootstrap_events(conn, 'tenant-a') == 1
    assert record_new_opportunities(conn, account_id='tenant-a', min_score=75) == []
    rows = conn.execute("SELECT event_key,account_id,score FROM opportunity_events").fetchall()
    assert len(rows) == 1
    assert rows[0]['event_key'] == 'tenant-a:ted:2026/s-1'
    assert rows[0]['score'] == 92
    conn.close()
