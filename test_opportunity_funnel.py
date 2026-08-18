import sqlite3

from decision_log import ensure_decision_table, funnel_counts
from opportunity_funnel import classify, record_funnel_decision


def test_classifier_is_deterministic_and_explainable():
    item = {"source": "TED", "external_id": "A", "score": 82, "market": "EU", "deadline": "2026-09-01"}
    decision, reason, features = classify(item, True)
    assert decision == "RELEVANT"
    assert reason == "HIGH_COMMERCIAL_SCORE"
    assert features["is_new"] is True
    assert features["market"] == "EU"


def test_funnel_writes_auditable_decision():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    item = {"source": "TED", "external_id": "A", "score": 31, "market": "EU"}
    decision, reason = record_funnel_decision(conn, item, False)
    assert decision == "LOW_SCORE"
    assert reason == "SCORE_BELOW_55"
    assert funnel_counts(conn) == {"LOW_SCORE": 1}
