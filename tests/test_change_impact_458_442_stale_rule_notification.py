"""Failing-before composition probe for #458 rule drift × #442 notification eventing.

A superseded decision rule must not silently authorize a new high-match event
that can progress into push delivery as though the score were current evidence.
"""

import sqlite3

from decision_log import ensure_decision_table, record_decision
from notification_events import record_new_opportunities


OLD_RULE = "commercial-v2+lot-v1+capability-v2+economic-fit-v3"
CURRENT_458_RULE = "commercial-v2.1+lot-v1+capability-v2+economic-fit-v3"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT,
            buyer TEXT,
            country TEXT,
            url TEXT,
            deadline TEXT,
            publication_date TEXT,
            score INTEGER,
            first_seen TEXT
        )"""
    )
    ensure_decision_table(conn)
    return conn


def _insert_recent_tender(conn, external_id):
    conn.execute(
        """INSERT INTO tenders(
               source,external_id,title,buyer,country,url,deadline,publication_date,score,first_seen
           ) VALUES('TEST',?,?,?,?,?,?,?,1,datetime('now'))""",
        (
            external_id,
            external_id,
            "Buyer",
            "PRT",
            "https://example.invalid/tender",
            "2099-01-01",
            "2026-08-25",
        ),
    )
    conn.commit()


def test_superseded_rule_score_must_not_create_current_high_match_event():
    conn = _conn()
    _insert_recent_tender(conn, "stale-rule")
    record_decision(
        conn,
        "TEST",
        "stale-rule",
        "QUALIFIED",
        "historical semantic rule",
        score=95,
        account_id="account-a",
        rule_version=OLD_RULE,
    )

    events = record_new_opportunities(conn, account_id="account-a", min_score=75)

    assert CURRENT_458_RULE != OLD_RULE
    assert events == [], (
        "superseded decision semantics must not authorize a new current "
        "high-match notification event"
    )
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0] == 0


def test_current_rule_score_can_create_high_match_event():
    conn = _conn()
    _insert_recent_tender(conn, "current-rule")
    record_decision(
        conn,
        "TEST",
        "current-rule",
        "QUALIFIED",
        "current semantic rule",
        score=95,
        account_id="account-a",
        rule_version=CURRENT_458_RULE,
    )

    events = record_new_opportunities(conn, account_id="account-a", min_score=75)

    assert len(events) == 1
    assert events[0]["event_key"] == "account-a:test:current-rule"
    assert events[0]["score"] == 95
