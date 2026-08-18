"""Tests for the mobile alert feed contract."""
import sqlite3
from datetime import datetime, timedelta, timezone

from notification_events import ensure_event_table, record_new_opportunities


def test_event_feed_is_idempotent_and_has_delivery_state():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
        country TEXT, url TEXT, deadline TEXT, profile_reason TEXT,
        profile_score INTEGER, score INTEGER, first_seen TEXT
    )""")
    recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""INSERT INTO tenders
        (id, source, external_id, title, country, url, deadline,
         profile_reason, profile_score, score, first_seen)
        VALUES (1,'TED','2026/S-1','Pavilhão industrial','ES',
                'https://example.invalid/1','2099-01-01','perfil: pavilhões',
                94,94,?)""", (recent,))
    ensure_event_table(conn)
    first = record_new_opportunities(conn, min_score=75)
    second = record_new_opportunities(conn, min_score=75)
    assert len(first) == 1
    assert len(second) == 0
    event = conn.execute("SELECT delivered_at FROM opportunity_events WHERE tender_id=1").fetchone()
    assert event[0] is None
    conn.execute("UPDATE opportunity_events SET delivered_at='2026-08-18T17:01:00+00:00' WHERE tender_id=1")
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE tender_id=1").fetchone()[0] is not None
    conn.close()
