import os


def test_provider_preflight_does_not_require_auth(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "https://app.example")

    import api

    client = api.APP.test_client()
    response = client.options(
        "/api/v1/profile",
        headers={
            "Origin": "https://app.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.example"


def test_provider_mode_rejects_wildcard_cors(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "*")

    import api

    client = api.APP.test_client()
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
