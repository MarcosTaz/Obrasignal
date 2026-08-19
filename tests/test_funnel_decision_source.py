import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_persist_and_classify_uses_match_pipeline_decision():
    from decision_log import latest_decision
    from funnel_integration import persist_and_classify

    item = {
        "source": "TED",
        "external_id": "CANONICAL-1",
        "title": "Construção de cobertura industrial",
        "description": "Execução e montagem.",
        "cpv": "45260000",
        "market": "PT",
        "score": 90,
        "profile_score": 90,
        "value_numeric": 150000,
        "deadline": None,
    }

    conn = _conn()
    decision, reason = persist_and_classify(conn, item, True, account_id="empresa-a")

    saved = latest_decision(conn, "TED", "CANONICAL-1", account_id="empresa-a")
    assert decision in {"QUALIFIED", "REVIEW", "REJECT"}
    assert saved["decision"] == decision
    assert saved["reason"] == reason
    assert saved["features"]["explanation"]["factors"]
    assert decision not in {"RELEVANT", "LOW_SCORE", "REJECTED"}
    conn.close()
