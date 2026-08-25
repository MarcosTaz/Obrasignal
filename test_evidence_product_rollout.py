import api
from decision_presentation import present_decision


def _decision():
    return {
        "decision": "QUALIFIED",
        "reason": "compatível",
        "score": 80,
        "rule_version": "commercial-v2",
        "features": {
            "explanation": {
                "factors": [],
                "negative_factors": [],
                "evidence": {
                    "state": "READY",
                    "confidence": "HIGH",
                    "sources": [{"source": "TED", "field_name": "deadline"}],
                    "missing": [],
                    "conflict_count": 0,
                },
            },
            # This private snapshot must never be copied into the API row.
            "decision_evidence": {
                "state": "READY",
                "graph": {"tenant_id": "company-a", "nodes": [{"private": "profile"}]},
            },
        },
    }


def _row():
    return {
        "id": 1,
        "source": "TED",
        "external_id": "E-1",
        "deadline": "2099-01-01",
    }


def test_api_hides_persisted_evidence_when_feature_is_disabled(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", raising=False)
    monkeypatch.delenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", raising=False)
    rendered = api._row(_row(), _decision())

    assert "evidence" not in rendered["explanation"]
    assert "decision_evidence" not in rendered
    serialized = repr(rendered)
    assert "tenant_id" not in serialized
    assert "company-a" not in serialized
    assert "'private': 'profile'" not in serialized


def test_api_exposes_only_redacted_evidence_when_enabled(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.delenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", raising=False)
    rendered = api._row(_row(), _decision())

    assert rendered["explanation"]["evidence"]["sources"][0]["source"] == "TED"
    assert "decision_evidence" not in rendered
    assert "tenant_id" not in repr(rendered)
    assert "private" not in repr(rendered)


def test_kill_switch_removes_already_persisted_evidence_without_removing_decision(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "true")
    rendered = api._row(_row(), _decision())

    assert rendered["account_decision"] == "QUALIFIED"
    assert "evidence" not in rendered["explanation"]


def test_malformed_rollout_config_fails_closed_at_read_boundary(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "sometimes")
    rendered = api._row(_row(), _decision())
    assert "evidence" not in rendered["explanation"]


def test_web_presentation_uses_same_read_time_rollout_policy(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.delenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", raising=False)
    assert present_decision(_decision())["evidence"]["state"] == "READY"

    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "true")
    presented = present_decision(_decision())
    assert presented["status"] == "QUALIFIED"
    assert presented["evidence"] is None
