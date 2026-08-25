import json

import cors_app
import preload


def _client(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "security-test-account")
    return cors_app.APP.test_client()


def test_api_security_headers_are_present(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/api/v1/health")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_malformed_integer_query_fails_closed_without_500(monkeypatch):
    client = _client(monkeypatch)
    for path in (
        "/api/v1/alerts?limit=banana",
        "/api/v1/opportunities?limit=banana",
        "/api/v1/opportunities?minscore=banana",
        "/api/v1/radar?limit=banana",
        "/api/v1/radar?minscore=banana",
    ):
        response = client.get(path)
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_query_parameter"


def test_pathological_query_text_is_bounded(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/api/v1/opportunities?q=" + ("x" * 201))
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_query_parameter", "parameter": "q"}

    response = client.get("/api/v1/latency?source=" + ("x" * 65))
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_query_parameter", "parameter": "source"}


def test_profile_write_requires_json_object(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/api/v1/profile", data="activity=builder", content_type="text/plain")
    assert response.status_code == 415
    assert response.get_json()["error"] == "content_type_must_be_application_json"

    response = client.post("/api/v1/profile", data="{bad", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "malformed_json"

    response = client.post("/api/v1/profile", data=json.dumps(["not", "an", "object"]), content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "json_object_required"


def test_profile_write_body_is_bounded(monkeypatch):
    client = _client(monkeypatch)
    payload = {"activity": "x" * (64 * 1024)}
    response = client.post("/api/v1/profile", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 413
    assert response.get_json()["error"] == "request_too_large"


def test_security_errors_do_not_echo_request_body(monkeypatch):
    client = _client(monkeypatch)
    secret_marker = "Bearer secret-should-never-echo"
    response = client.post("/api/v1/profile", data="{\"activity\":\"" + secret_marker + "\"", content_type="application/json")
    assert response.status_code == 400
    assert secret_marker not in response.get_data(as_text=True)


def test_source_health_does_not_expose_raw_exception_detail(monkeypatch):
    client = _client(monkeypatch)
    secret_marker = "token=secret-provider-value"
    monkeypatch.setattr(
        preload,
        "source_health_snapshot",
        lambda _conn: [{"source": "TEST", "status": "degraded", "last_error": f"https://provider.test/feed?{secret_marker}"}],
    )
    response = client.get("/api/v1/source-health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["items"][0]["last_error"] == "redacted"
    assert body["items"][0]["has_error"] is True
    assert secret_marker not in response.get_data(as_text=True)
