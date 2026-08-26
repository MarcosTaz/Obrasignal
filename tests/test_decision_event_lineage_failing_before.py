"""Failing-before proof for decision -> opportunity_event causal parentage.

Built on the exact Notification owner candidate so the probe exercises its real
latest-account-decision eligibility path without prescribing the repair schema.
"""
import sqlite3

from decision_log import record_decision
from notification_events import ensure_event_table, record_new_opportunities


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
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
    ensure_event_table(conn)
    return conn


def test_event_keeps_exact_decision_parent_after_same_score_supersession():
    conn = _conn()
    conn.execute(
        """INSERT INTO tenders(
               id,source,external_id,title,country,url,deadline,score,first_seen
           ) VALUES (1,'TED','LINEAGE-D1-D2','Synthetic','PRT','https://example.test',
                     '2099-01-01',5,datetime('now'))"""
    )
    conn.commit()

    record_decision(
        conn,
        "TED",
        "LINEAGE-D1-D2",
        "REVIEW",
        "first synthetic decision",
        score=90,
        features={"fixture": "D1"},
        rule_version="fixture-v1",
        account_id="account-a",
    )
    d1 = conn.execute(
        "SELECT id FROM opportunity_decisions WHERE account_id='account-a' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]

    created = record_new_opportunities(conn, account_id="account-a", min_score=75)
    assert len(created) == 1

    # A later decision deliberately has the same score. Score equality therefore
    # cannot reconstruct causal parent identity.
    record_decision(
        conn,
        "TED",
        "LINEAGE-D1-D2",
        "REVIEW",
        "second synthetic decision",
        score=90,
        features={"fixture": "D2"},
        rule_version="fixture-v2",
        account_id="account-a",
    )
    d2 = conn.execute(
        "SELECT id FROM opportunity_decisions WHERE account_id='account-a' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]
    assert d2 != d1

    event = conn.execute("SELECT * FROM opportunity_events").fetchone()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_events)")}
    assert event["account_id"] == "account-a"
    assert event["score"] == 90

    # Failing-before: dedupe/event score proves neither D1 nor D2 was the parent.
    # The owner repair may choose a different durable representation, but the
    # event must carry an equivalent exact parent reference that survives D2.
    assert "decision_id" in columns, (
        "DECISION_EVENT_PARENTAGE_AMBIGUOUS: durable event has account/opportunity/"
        "score but no exact decision parent; same-score D2 can silently become the "
        "apparent current decision during later audit reconstruction"
    )
    assert event["decision_id"] == d1
    conn.close()
