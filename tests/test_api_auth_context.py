import api


def test_profile_api_uses_request_identity_not_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")

    client = api.APP.test_client()
    response = client.post(
        "/api/v1/profile",
        json={
            "account_id": "account-b",
            "name": "Empresa A",
            "activity": "metalomecânica",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["account_id"] == "account-a"
    assert body["profile"]["account_id"] == "account-a"


def test_profiles_are_selected_from_request_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_PROFILE_DIR", str(tmp_path / "profiles"))
    client = api.APP.test_client()

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    assert client.post("/api/v1/profile", json={"name": "A"}).status_code == 200

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-b")
    assert client.post("/api/v1/profile", json={"name": "B"}).status_code == 200

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    a = client.get("/api/v1/profile").get_json()["profile"]
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-b")
    b = client.get("/api/v1/profile").get_json()["profile"]

    assert a["name"] == "A"
    assert b["name"] == "B"


def test_provider_cors_normalizes_github_pages_project_path(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "https://marcostaz.github.io/Obrasignal/")

    response = api.APP.test_client().options(
        "/api/v1/profile",
        headers={
            "Origin": "https://marcostaz.github.io",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://marcostaz.github.io"
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert "GET" in response.headers["Access-Control-Allow-Methods"]
