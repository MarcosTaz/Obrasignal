"""Failing-before composition probe for #458 rule-version drift × #461 Radar ranking.

The probe is intentionally mechanism-neutral: a decision produced under a
superseded semantic rule must not silently satisfy a positive current Radar
threshold as though it were current evidence.
"""

import sqlite3

from decision_log import ensure_decision_table, record_decision
from lifecycle_read_model import _ranked_radar_rows
from opportunity_lifecycle import ensure_lifecycle_table


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
            score INTEGER,
            title TEXT,
            deadline TEXT,
            publication_date TEXT
        )"""
    )
    ensure_lifecycle_table(conn)
    ensure_decision_table(conn)
    return conn


def _insert_tender(conn, external_id):
    # Keep lifecycle/actionability deliberately non-blocking so this probe
    # isolates semantic rule-version freshness rather than wall-clock expiry.
    conn.execute(
        "INSERT INTO tenders(source,external_id,score,title,deadline,publication_date) VALUES(?,?,?,?,?,?)",
        ("TEST", external_id, 1, external_id, "2099-01-01T12:00:00+00:00", "2026-08-25"),
    )
    conn.commit()


def test_positive_radar_threshold_must_not_treat_superseded_rule_score_as_current():
    conn = _conn()
    _insert_tender(conn, "stale-rule")

    # The exact score is intentionally synthetic; the invariant is about
    # semantic-version freshness, not weights or lifecycle timing.
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

    rows = _ranked_radar_rows(conn, "account-a", minscore=75, limit=10)

    assert CURRENT_458_RULE != OLD_RULE
    assert [row["external_id"] for row in rows] == [], (
        "a positive current Radar threshold must not accept a score whose "
        "decision semantic rule is superseded"
    )


def test_current_rule_decision_remains_eligible_for_positive_threshold():
    conn = _conn()
    _insert_tender(conn, "current-rule")

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

    rows = _ranked_radar_rows(conn, "account-a", minscore=75, limit=10)

    assert [row["external_id"] for row in rows] == ["current-rule"]
