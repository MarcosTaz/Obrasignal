import sqlite3

from decision_log import ensure_decision_table, record_decision
from radar_decision_feed import enrich_rows


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    return conn


def test_enrich_rows_exposes_persisted_decision_and_layers():
    conn = _db()
    record_decision(
        conn,
        "TED",
        "X-1",
        "QUALIFIED",
        "cumpre perfil",
        score=88,
        rule_version="test-v1",
        features={
            "profile_score": 86,
            "lot_score": 78,
            "lot_id": "LOT-1",
            "geography": {"score": 5, "reason": "cidade prioritária"},
            "capability_evidence": {"evidence_count": 2, "reason": "capacidades encontradas"},
            "economic_fit": {"score": 100, "status": "FAVOURABLE", "reason": "valor dentro do intervalo"},
        },
    )

    rows = enrich_rows(conn, [{"source": "TED", "external_id": "X-1", "title": "Teste"}])
    summary = rows[0]["decision_summary"]

    assert summary["status"] == "QUALIFIED"
    assert summary["score"] == 88
    assert summary["rule_version"] == "test-v1"
    layers = {layer["key"]: layer for layer in summary["layers"]}
    assert layers["profile"]["score"] == 86
    assert layers["lot"]["score"] == 78
    assert layers["geography"]["score"] == 5
    assert layers["economic_fit"]["score"] == 100
    assert layers["capability"]["kind"] == "evidence"
    assert layers["capability"]["score"] is None


def test_enrich_rows_does_not_invent_decision():
    conn = _db()

    rows = enrich_rows(conn, [{"source": "TED", "external_id": "X-2", "title": "Teste"}])

    assert rows[0]["decision_summary"]["status"] == "SEM DECISÃO"
    assert rows[0]["decision_summary"]["score"] is None
    assert rows[0]["decision_summary"]["layers"] == []


def test_enrich_rows_exposes_hard_blockers_separately():
    conn = _db()
    record_decision(
        conn,
        "TED",
        "X-3",
        "REJECTED",
        "CAPABILITY_BLOCKER",
        features={"hard_capability_blockers": ["CPV fora", "procedimento excluído"]},
    )

    summary = enrich_rows(conn, [{"source": "TED", "external_id": "X-3"}])[0]["decision_summary"]
    blocker = next(layer for layer in summary["layers"] if layer["key"] == "blockers")
    assert blocker["kind"] == "blocker"
    assert blocker["evidence_count"] == 2
