import api
import cors_app


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return _Result(self._row)

    def close(self):
        return None


def _decision_with_customer_evidence():
    return {
        "decision": "REVIEW",
        "reason": "integration",
        "score": 61,
        "rule_version": "q080-security-integration",
        "decided_at": "2026-08-25T00:00:00+00:00",
        "features": {
            "explanation": {
                "summary": "bounded explanation",
                "evidence": {
                    "status": "SUPPORTED",
                    "confidence": "HIGH",
                    "source": "TED",
                },
            }
        },
    }


def _detail_client(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "integration-tenant")
    row = {
        "id": 1,
        "source": "TED",
        "external_id": "q080-security-1",
        "title": "Integration opportunity",
        "deadline": None,
        "is_actionable": None,
    }
    monkeypatch.setattr(api, "_db", lambda: _Connection(row))
    monkeypatch.setattr(api, "ensure_account", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "ensure_lifecycle_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        api,
        "_latest_decisions",
        lambda *_args, **_kwargs: {("TED", "q080-security-1"): _decision_with_customer_evidence()},
    )
    monkeypatch.setattr(
        api,
        "get_workflow",
        lambda *_args, **_kwargs: {"status": "NEW", "note": None, "updated_at": None},
    )
    return cors_app.APP.test_client()


def _assert_security_headers(response):
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_disabled_q080_evidence_survives_security_boundary_as_hidden(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "false")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "false")
    response = _detail_client(monkeypatch).get("/api/v1/opportunities/1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["account_decision"] == "REVIEW"
    assert body["explanation"]["summary"] == "bounded explanation"
    assert "evidence" not in body["explanation"]
    _assert_security_headers(response)


def test_enabled_q080_customer_evidence_is_not_erased_by_security_boundary(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "false")
    response = _detail_client(monkeypatch).get("/api/v1/opportunities/1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["explanation"]["evidence"]["status"] == "SUPPORTED"
    assert body["explanation"]["evidence"]["source"] == "TED"
    _assert_security_headers(response)


def test_q080_kill_switch_wins_through_hardened_http_boundary(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "true")
    response = _detail_client(monkeypatch).get("/api/v1/opportunities/1")
    assert response.status_code == 200
    assert "evidence" not in response.get_json()["explanation"]
    _assert_security_headers(response)
