import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_pipeline_decisions_are_isolated_by_account():
    from funnel_integration import persist_and_classify
    from decision_log import latest_decision, funnel_counts
    from opportunity_match_pipeline import evaluate_row

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

    evaluation = evaluate_row(item)
    assert "explanation" in evaluation
    assert evaluation["explanation"]["factors"]
    assert {factor["key"] for factor in evaluation["explanation"]["factors"]} >= {
        "profile", "lot", "geography", "capability", "economic_fit"
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


def test_sync_without_explicit_account_evaluates_all_active_accounts():
    from account_registry import ensure_account
    from decision_log import latest_decision
    from sync_funnel_hook import record_sync_decisions

    item = {
        "source": "TED",
        "external_id": "X-2",
        "score": 85,
        "title": "Cobertura industrial",
        "description": "Cobertura e estrutura metálica.",
        "cpv": "45261210",
        "market": "PT",
        "deadline": None,
        "first_seen": "same",
        "last_seen": "same",
    }

    conn = _conn()
    ensure_account(conn, "empresa-a")
    ensure_account(conn, "empresa-b")
    recorded = record_sync_decisions(conn, [item])

    assert recorded == 2
    assert latest_decision(conn, "TED", "X-2", account_id="empresa-a") is not None
    assert latest_decision(conn, "TED", "X-2", account_id="empresa-b") is not None
    conn.close()
