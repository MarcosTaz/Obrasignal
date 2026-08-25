import sqlite3
from datetime import datetime, timedelta, timezone

from api import _row
from decision_log import ensure_decision_table, latest_decision, record_decision
from decision_presentation import present_decision


def test_historical_decision_without_evidence_remains_readable_and_presentable(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    record_decision(conn, "TED", "legacy-without-evidence", "REVIEW", "historical decision", score=61, rule_version="legacy-rule-v1", features={"profile_score": 61}, account_id="company-a")
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


def _decision_with_evidence():
    return {"decision": "REVIEW", "reason": "integration", "score": 61, "rule_version": "q080-integration", "decided_at": "2026-08-25T00:00:00+00:00", "features": {"explanation": {"summary": "bounded explanation", "evidence": {"status": "SUPPORTED", "confidence": "HIGH"}}}}


def test_q080_gating_preserves_current_main_expired_deadline_actionability(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "false")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "false")
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    presented = _row({"deadline": yesterday, "is_actionable": None}, _decision_with_evidence())
    assert presented["deadline_status"]["state"] == "closed"
    assert presented["is_actionable"] is False
    assert presented["is_open"] is False
    assert "evidence" not in presented["explanation"]


def test_q080_gating_preserves_current_main_date_only_today_unknown_semantics(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "false")
    today = datetime.now(timezone.utc).date().isoformat()
    presented = _row({"deadline": today, "is_actionable": None}, _decision_with_evidence())
    assert presented["deadline_status"]["state"] == "unknown"
    assert presented["is_actionable"] is True
    assert presented["is_open"] is False
    assert presented["explanation"]["evidence"]["status"] == "SUPPORTED"


def test_q080_gating_preserves_explicit_lifecycle_precedence(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "true")
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    presented = _row({"deadline": yesterday, "is_actionable": True}, _decision_with_evidence())
    assert presented["deadline_status"]["state"] == "closed"
    assert presented["is_actionable"] is True
    assert presented["is_open"] is False
    assert "evidence" not in presented["explanation"]
