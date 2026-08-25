import sqlite3

from decision_log import ensure_decision_table, latest_decision, record_decision
from decision_presentation import present_decision


def test_historical_decision_without_evidence_remains_readable_and_presentable(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    record_decision(
        conn,
        "TED",
        "legacy-without-evidence",
        "REVIEW",
        "historical decision",
        score=61,
        rule_version="legacy-rule-v1",
        features={"profile_score": 61},
        account_id="company-a",
    )

    persisted = latest_decision(conn, "TED", "legacy-without-evidence", account_id="company-a")
    assert persisted["decision"] == "REVIEW"
    assert "decision_evidence" not in persisted["features"]

    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    presented = present_decision(persisted)
    assert presented["status"] == "REVIEW"
    assert presented["reason"] == "historical decision"
    assert presented["score"] == 61
    assert presented["evidence"] is None
    assert any(line["label"] == "Perfil da empresa" for line in presented["lines"])
