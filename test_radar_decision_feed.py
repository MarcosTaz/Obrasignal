import sqlite3

from decision_log import ensure_decision_table, record_decision
from radar_decision_feed import enrich_rows


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    return conn


def test_enrich_rows_exposes_persisted_decision():
    conn = _db()
    record_decision(
        conn,
        "TED",
        "X-1",
        "QUALIFIED",
        "cumpre perfil",
        score=88,
        rule_version="test-v1",
    )

    rows = enrich_rows(conn, [{"source": "TED", "external_id": "X-1", "title": "Teste"}])

    assert rows[0]["decision_summary"]["status"] == "QUALIFIED"
    assert rows[0]["decision_summary"]["score"] == 88
    assert rows[0]["decision_summary"]["rule_version"] == "test-v1"


def test_enrich_rows_does_not_invent_decision():
    conn = _db()

    rows = enrich_rows(conn, [{"source": "TED", "external_id": "X-2", "title": "Teste"}])

    assert rows[0]["decision_summary"]["status"] == "SEM DECISÃO"
    assert rows[0]["decision_summary"]["score"] is None
