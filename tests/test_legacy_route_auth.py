import api


def test_legacy_routes_require_authentication_in_provider_mode(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    client = api.APP.test_client()

    assert client.get("/radar").status_code == 401
    assert client.get("/opportunity/1").status_code == 401
    assert client.get("/api/v1/source-health").status_code == 401
    assert client.get("/api/v1/latency").status_code == 401
    assert client.get("/api/v1/latency-health").status_code == 401
