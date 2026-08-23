import sqlite3
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import api
import account_registry
import auth_context_jwt


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
    load_profile(Identity.account_id)

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


def test_profile_get_and_post_share_warm_jwks_cache(monkeypatch, tmp_path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "profile-key", "use": "sig", "alg": "RS256"})
    issuer = "https://profile.example/auth/v1"
    now = int(time.time())
    token = jwt.encode(
        {"sub": "profile-user", "iss": issuer, "aud": "authenticated", "iat": now, "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "profile-key"},
    )
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "profiles.db"))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", issuer)
    monkeypatch.setattr(auth_context_jwt, "_verifier", None)
    monkeypatch.setattr(auth_context_jwt, "_verifier_config", None)
    calls = 0

    def fetch(_self):
        nonlocal calls
        calls += 1
        return {"profile-key": jwk}

    monkeypatch.setattr(auth_context_jwt.JwtVerifier, "_fetch_jwks", fetch)
    monkeypatch.setattr(api, "bootstrap_account", lambda account_id: 0)
    headers = {"Authorization": f"Bearer {token}"}
    client = api.APP.test_client()

    assert client.get("/api/v1/profile", headers=headers).status_code == 200
    assert client.post("/api/v1/profile", headers=headers, json={"name": "Empresa"}).status_code == 200
    assert calls == 1


def test_all_authenticated_hot_paths_share_one_jwks_fetch(monkeypatch):
    api._preload._app.init_db()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "hot-path-key", "use": "sig", "alg": "RS256"})
    issuer = "https://hot-path.example/auth/v1"
    now = int(time.time())
    token = jwt.encode(
        {"sub": "jwks-hot-path-test", "iss": issuer, "aud": "authenticated", "iat": now, "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "hot-path-key"},
    )
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", issuer)
    monkeypatch.setattr(auth_context_jwt, "_verifier", None)
    monkeypatch.setattr(auth_context_jwt, "_verifier_config", None)
    calls = 0

    def fetch(_self):
        nonlocal calls
        calls += 1
        return {"hot-path-key": jwk}

    monkeypatch.setattr(auth_context_jwt.JwtVerifier, "_fetch_jwks", fetch)
    monkeypatch.setattr(api, "bootstrap_account", lambda account_id: 0)
    headers = {"Authorization": f"Bearer {token}"}
    client = api.APP.test_client()

    assert client.get("/api/v1/profile", headers=headers).status_code == 200
    assert client.post("/api/v1/profile", headers=headers, json={}).status_code == 200
    assert client.get("/api/v1/opportunities", headers=headers).status_code == 200
    assert client.get("/api/v1/stats", headers=headers).status_code == 200
    assert client.get("/api/v1/billing/status", headers=headers).status_code == 200
    assert calls == 1


def test_authenticated_hot_paths_work_from_bootstrap_during_remote_outage(monkeypatch):
    api._preload._app.init_db()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "bootstrap-key", "use": "sig", "alg": "RS256"})
    issuer = "https://bootstrap.example/auth/v1"
    now = int(time.time())
    token = jwt.encode(
        {"sub": "jwks-bootstrap-test", "iss": issuer, "aud": "authenticated", "iat": now, "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "bootstrap-key"},
    )
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", issuer)
    monkeypatch.setenv("OBRASIGNAL_JWKS_BOOTSTRAP_JSON", json.dumps({"keys": [jwk]}))
    monkeypatch.setattr(auth_context_jwt, "_verifier", None)
    monkeypatch.setattr(auth_context_jwt, "_verifier_config", None)
    calls = 0

    def unavailable(_self):
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(auth_context_jwt.JwtVerifier, "_fetch_jwks", unavailable)
    monkeypatch.setattr(api, "bootstrap_account", lambda account_id: 0)
    headers = {"Authorization": f"Bearer {token}"}
    client = api.APP.test_client()

    assert client.get("/api/v1/profile", headers=headers).status_code == 200
    assert client.post("/api/v1/profile", headers=headers, json={}).status_code == 200
    assert client.get("/api/v1/opportunities", headers=headers).status_code == 200
    assert client.get("/api/v1/stats", headers=headers).status_code == 200
    assert client.get("/api/v1/billing/status", headers=headers).status_code == 200
    assert calls == 0


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/profile"),
        ("post", "/api/v1/profile"),
        ("get", "/api/v1/opportunities"),
        ("get", "/api/v1/stats"),
        ("get", "/api/v1/billing/status"),
    ],
)
def test_authenticated_endpoints_return_503_when_jwks_unavailable(monkeypatch, method, path):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    unavailable = lambda: (_ for _ in ()).throw(auth_context_jwt.JwksUnavailableError())
    monkeypatch.setattr(api, "configured_identity", unavailable)
    monkeypatch.setattr(account_registry, "configured_identity", unavailable)

    response = getattr(api.APP.test_client(), method)(path)

    assert response.status_code == 503
    assert response.get_json()["error"] == "authentication_service_unavailable"


def test_invalid_token_still_returns_401(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://invalid-token.example/auth/v1")

    response = api.APP.test_client().get(
        "/api/v1/profile", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
