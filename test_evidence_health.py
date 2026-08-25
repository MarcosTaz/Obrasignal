import app


def test_health_reports_evidence_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", raising=False)
    monkeypatch.delenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", raising=False)
    response = app.APP.test_client().get("/api/v1/health")
    assert response.status_code == 200
    evidence = response.get_json()["capabilities"]["evidence"]
    assert evidence == {"enabled": False, "state": "DISABLED", "configuration_error": None}


def test_health_reports_enabled_without_exposing_configuration(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.delenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", raising=False)
    response = app.APP.test_client().get("/api/v1/health")
    evidence = response.get_json()["capabilities"]["evidence"]
    assert evidence["enabled"] is True
    assert evidence["state"] == "ENABLED"
    assert "OBRASIGNAL_FEATURE" not in response.get_data(as_text=True)


def test_health_fails_capability_closed_on_malformed_rollout(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "sometimes")
    response = app.APP.test_client().get("/api/v1/health")
    assert response.status_code == 200
    evidence = response.get_json()["capabilities"]["evidence"]
    assert evidence["enabled"] is False
    assert evidence["state"] == "DISABLED"
    assert evidence["configuration_error"] == "RuntimeError"
    assert "sometimes" not in response.get_data(as_text=True)
