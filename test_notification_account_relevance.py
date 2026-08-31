"""Tenant-safe relevance regressions for account-scoped notification events."""
import sqlite3
from datetime import datetime, timedelta, timezone

from decision_log import record_decision
from notification_events import ensure_event_table, record_new_opportunities


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


def _recent():
    return (datetime.now(timezone.utc) - timedelta(seconds=20)).strftime("%Y-%m-%d %H:%M:%S")


def test_notification_uses_account_score_not_global_tender_score():
    conn = _conn()
    conn.execute(
        """INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen)
           VALUES (1,'TED','TENANT-1','Global score high','2099-01-01',99,?)""",
        (_recent(),),
    )
    record_decision(conn, "TED", "TENANT-1", "QUALIFIED", "A high", score=91, account_id="account-a")
    record_decision(conn, "TED", "TENANT-1", "REJECT", "B low", score=35, account_id="account-b")

    a_events = record_new_opportunities(conn, account_id="account-a", min_score=75)
    b_events = record_new_opportunities(conn, account_id="account-b", min_score=75)

    assert len(a_events) == 1
    assert a_events[0]["score"] == 91
    assert b_events == []
    rows = conn.execute("SELECT account_id,score FROM opportunity_events ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [("account-a", 91)]
    conn.close()


def test_latest_account_decision_controls_notification_eligibility():
    conn = _conn()
    conn.execute(
        """INSERT INTO tenders(id,source,external_id,title,deadline,score,first_seen)
           VALUES (2,'TED','TENANT-2','Decision changed','2099-01-01',99,?)""",
        (_recent(),),
    )
    record_decision(conn, "TED", "TENANT-2", "QUALIFIED", "older high", score=92, account_id="account-a")
    record_decision(conn, "TED", "TENANT-2", "REJECT", "new low", score=30, account_id="account-a")

    assert record_new_opportunities(conn, account_id="account-a", min_score=75) == []
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0] == 0
    conn.close()
