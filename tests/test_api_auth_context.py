import sqlite3

import api


def test_profile_api_uses_request_identity_not_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "profiles.db"))
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
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "profiles.db"))
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


def test_authenticated_profile_read_survives_concurrent_sync_writer(monkeypatch, tmp_path):
    from account_registry import ensure_account
    from company_profile import load_profile

    class Identity:
        account_id = "account-a"
        authenticated = True

    db_path = tmp_path / "production.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))

    def connect():
        conn = sqlite3.connect(db_path, timeout=0.001)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=1")
        return conn

    bootstrap = connect()
    ensure_account(bootstrap, Identity.account_id)
    bootstrap.close()
    load_profile(Identity.account_id)  # Initialize durable profile storage.

    locker = connect()
    locker.execute("BEGIN IMMEDIATE")
    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    monkeypatch.setattr(api._preload._app, "db", connect)
    try:
        response = api.APP.test_client().get("/api/v1/profile")
    finally:
        locker.rollback()
        locker.close()

    assert response.status_code == 200
    assert response.get_json()["account_id"] == Identity.account_id
    assert response.get_json()["authenticated"] is True


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

    # 204 No Content is the normal preflight response and is explicitly
    # supported by the CORS protocol.
    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "https://marcostaz.github.io"
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert "GET" in response.headers["Access-Control-Allow-Methods"]


def test_provider_mode_rejects_missing_bearer_on_protected_route(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://example.supabase.co")
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "https://marcostaz.github.io")

    response = api.APP.test_client().get("/api/v1/profile")

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"


def test_provider_mode_keeps_health_public(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://example.supabase.co")
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "https://marcostaz.github.io")

    response = api.APP.test_client().get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
