import sqlite3

from decision_log import funnel_counts, latest_decision, record_decision
from opportunity_funnel import record_funnel_decision


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_decisions_are_isolated_by_account():
    conn = _conn()
    record_decision(conn, "TED", "X1", "RELEVANT", "A", score=80, account_id="a")
    record_decision(conn, "TED", "X1", "LOW_SCORE", "B", score=40, account_id="b")

    assert latest_decision(conn, "TED", "X1", account_id="a")["decision"] == "RELEVANT"
    assert latest_decision(conn, "TED", "X1", account_id="b")["decision"] == "LOW_SCORE"
    assert funnel_counts(conn, account_id="a") == {"RELEVANT": 1}
    assert funnel_counts(conn, account_id="b") == {"LOW_SCORE": 1}


def test_legacy_calls_default_to_default_account():
    conn = _conn()
    record_decision(conn, "TED", "X2", "RELEVANT", "legacy", score=75)

    decision = latest_decision(conn, "TED", "X2")
    assert decision["account_id"] == "default"
    assert funnel_counts(conn) == {"RELEVANT": 1}


def test_funnel_passes_account_identity_without_changing_classification():
    conn = _conn()
    item = {"source": "TED", "external_id": "X3", "score": 80}

    decision, reason = record_funnel_decision(conn, item, is_new=True, account_id="company-a")

    assert decision == "RELEVANT"
    assert reason == "HIGH_COMMERCIAL_SCORE"
    stored = latest_decision(conn, "TED", "X3", account_id="company-a")
    assert stored["account_id"] == "company-a"
