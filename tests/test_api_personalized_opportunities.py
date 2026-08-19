import sqlite3


def _decision_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_decision_map_isolated_by_account():
    from decision_log import record_decision
    from api import _decision_map

    conn = _decision_conn()
    record_decision(
        conn,
        "TED",
        "X-1",
        "QUALIFIED",
        "Empresa A encaixa",
        score=91,
        features={"explanation": {"factors": [{"key": "profile"}]}},
        account_id="empresa-a",
    )
    record_decision(
        conn,
        "TED",
        "X-1",
        "REJECT",
        "Empresa B excluiu este procedimento",
        score=20,
        features={"explanation": {"factors": [{"key": "profile"}]}},
        account_id="empresa-b",
    )

    row = {"source": "TED", "external_id": "X-1"}
    a = _decision_map(conn, [row], "empresa-a")[("TED", "X-1")]
    b = _decision_map(conn, [row], "empresa-b")[("TED", "X-1")]

    assert a["decision"] == "QUALIFIED"
    assert a["score"] == 91
    assert b["decision"] == "REJECT"
    assert b["score"] == 20
    conn.close()


def test_decision_map_handles_missing_decision():
    from api import _decision_map

    conn = _decision_conn()
    row = {"source": "TED", "external_id": "NO-DECISION"}
    assert _decision_map(conn, [row], "empresa-a") == {}
    conn.close()
