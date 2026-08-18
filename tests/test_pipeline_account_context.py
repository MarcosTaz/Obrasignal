import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_pipeline_decisions_are_isolated_by_account():
    from funnel_integration import persist_and_classify
    from decision_log import latest_decision, funnel_counts

    item = {
        "source": "TED",
        "external_id": "X-1",
        "score": 80,
        "title": "Estruturas metálicas",
        "description": "Fabrico e montagem.",
        "cpv": "45213200",
        "market": "PT",
        "deadline": None,
    }

    conn = _conn()
    persist_and_classify(conn, item, True, account_id="empresa-a")
    persist_and_classify(conn, item, True, account_id="empresa-b")

    a = latest_decision(conn, "TED", "X-1", account_id="empresa-a")
    b = latest_decision(conn, "TED", "X-1", account_id="empresa-b")
    assert a is not None
    assert b is not None
    assert a["account_id"] == "empresa-a"
    assert b["account_id"] == "empresa-b"
    assert funnel_counts(conn, "empresa-a") == {"RELEVANT": 1}
    assert funnel_counts(conn, "empresa-b") == {"RELEVANT": 1}
    conn.close()
