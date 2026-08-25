import sqlite3

import funnel_integration
from decision_log import ensure_decision_table, latest_decision


def test_funnel_persists_full_snapshot_but_exposes_only_redacted_explanation(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id="default": {
            "activity": "Construção",
            "services": ["reabilitação"],
            "countries": ["PRT"],
            "cpv_prefixes": ["4521"],
            "min_value": 100000,
            "max_value": 500000,
        },
    )
    item = {
        "source": "TED",
        "external_id": "FUNNEL-EVIDENCE-1",
        "title": "Reabilitação de escola",
        "description": "Obras de reabilitação",
        "buyer": "Município",
        "country": "PRT",
        "cpv": "45214200",
        "value": "250000 EUR",
        "deadline": "2099-09-30T12:00:00+00:00",
        "procedure_type": "OPEN",
        "publication_date": "2026-08-24T00:00:00+00:00",
        "last_seen": "2026-08-25T02:00:00+00:00",
    }

    decision, _ = funnel_integration.persist_and_classify(
        conn,
        item,
        True,
        account_id="company-a",
    )
    persisted = latest_decision(conn, "TED", "FUNNEL-EVIDENCE-1", account_id="company-a")

    assert persisted["decision"] == decision
    assert persisted["features"]["decision_evidence"]["state"] == "READY"
    assert persisted["features"]["decision_evidence"]["graph"]["tenant_id"] == "company-a"
    public = persisted["features"]["explanation"]["evidence"]
    assert public["state"] == "READY"
    assert public["sources"]
    assert "graph" not in public
    assert "tenant_id" not in repr(public)
