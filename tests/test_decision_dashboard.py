import sqlite3

from opportunity_match_pipeline import RULE_VERSION


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_dashboard_decision_is_scoped_to_account():
    from decision_dashboard import get_presented_decision
    from decision_log import record_decision

    conn = _conn()
    record_decision(
        conn,
        "TED",
        "X-100",
        "QUALIFIED",
        "boa compatibilidade",
        score=88,
        features={"profile_score": 88},
        account_id="empresa-a",
        rule_version=RULE_VERSION,
    )
    record_decision(
        conn,
        "TED",
        "X-100",
        "REJECT",
        "fora da capacidade",
        score=31,
        features={"profile_score": 31},
        account_id="empresa-b",
        rule_version=RULE_VERSION,
    )

    a = get_presented_decision(conn, "TED", "X-100", account_id="empresa-a")
    b = get_presented_decision(conn, "TED", "X-100", account_id="empresa-b")

    assert a["status"] == "QUALIFIED"
    assert b["status"] == "REJECT"
    assert a["score"] == 88
    assert b["score"] == 31
    conn.close()


def test_dashboard_does_not_present_superseded_rule_as_current_truth():
    from decision_dashboard import get_presented_decision
    from decision_log import record_decision

    conn = _conn()
    record_decision(
        conn,
        "TED",
        "X-stale",
        "QUALIFIED",
        "old semantics",
        score=99,
        account_id="empresa-a",
        rule_version="superseded-rule",
    )

    presented = get_presented_decision(conn, "TED", "X-stale", account_id="empresa-a")

    assert presented["status"] == "SEM DECISÃO"
    assert presented["score"] is None
    conn.close()
