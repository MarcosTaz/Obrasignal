import json
import socket
import ssl
from urllib.error import HTTPError, URLError

import pytest

import auth_context_jwt as auth_jwt
from auth_context_jwt import JwksUnavailableError, JwtVerifier, authentication_health, production_verifier


def _reset_verifier():
    auth_jwt._verifier = None
    auth_jwt._verifier_config = None


def _configured_provider(monkeypatch, issuer="https://project-a.supabase.co"):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", issuer)
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("OBRASIGNAL_JWKS_URL", raising=False)
    _reset_verifier()
    return production_verifier()


def _force_failure(verifier, monkeypatch, exc):
    monkeypatch.setattr(
        verifier,
        "_fetch_jwks",
        lambda: (_ for _ in ()).throw(exc),
    )
    try:
        verifier._key_for("unknown")
    except JwksUnavailableError:
        pass
    else:
        raise AssertionError("provider failure must fail closed")


def test_authentication_health_reports_missing_provider_config(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.delenv("OBRASIGNAL_JWT_ISSUER", raising=False)
    monkeypatch.delenv("OBRASIGNAL_JWT_AUDIENCE", raising=False)
    _reset_verifier()

    assert authentication_health() == {
        "mode": "provider",
        "config_present": False,
        "provider_status": "misconfigured",
    }


def test_authentication_health_reports_malformed_issuer_before_network(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "project-a.supabase.co/auth/v1")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("OBRASIGNAL_JWKS_URL", raising=False)
    _reset_verifier()

    assert authentication_health() == {
        "mode": "provider",
        "config_present": False,
        "provider_status": "misconfigured",
        "provider_kind": "invalid",
        "provider_error": "invalid_issuer_url",
    }
    with pytest.raises(RuntimeError, match="invalid_issuer_url"):
        production_verifier()


def test_authentication_health_rejects_provider_url_credentials(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://user:password@identity.example.test/issuer")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("OBRASIGNAL_JWKS_URL", raising=False)
    _reset_verifier()

    health = authentication_health()
    assert health["config_present"] is False
    assert health["provider_status"] == "misconfigured"
    assert health["provider_error"] == "invalid_issuer_url"
    assert "user" not in json.dumps(health)
    assert "password" not in json.dumps(health)


def test_authentication_health_rejects_malformed_oidc_jwks_override(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://identity.example.test/issuer")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv("OBRASIGNAL_JWKS_URL", "identity.example.test/jwks")
    _reset_verifier()

    assert authentication_health() == {
        "mode": "provider",
        "config_present": False,
        "provider_status": "misconfigured",
        "provider_kind": "oidc",
        "provider_error": "invalid_jwks_url",
    }


def test_jwt_verifier_rejects_invalid_provider_url_without_fetching():
    with pytest.raises(RuntimeError, match="invalid_issuer_url"):
        JwtVerifier("not-an-absolute-provider-url")


def test_authentication_health_is_passive_before_first_jwks_fetch(monkeypatch):
    _configured_provider(monkeypatch)

    assert authentication_health() == {
        "mode": "provider",
        "config_present": True,
        "provider_status": "uninitialized",
        "provider_kind": "supabase",
        "provider_error": None,
    }


def test_authentication_health_reports_ready_after_successful_key_refresh(monkeypatch):
    verifier = _configured_provider(monkeypatch)
    monkeypatch.setattr(verifier, "_fetch_jwks", lambda: {"known": {"kid": "known"}})

    assert verifier._key_for("known")["kid"] == "known"
    assert authentication_health() == {
        "mode": "provider",
        "config_present": True,
        "provider_status": "ready",
        "provider_kind": "supabase",
        "provider_error": None,
    }


def test_authentication_health_reports_timeout_without_exception_text(monkeypatch):
    verifier = _configured_provider(monkeypatch)
    _force_failure(verifier, monkeypatch, TimeoutError("secret-provider.example timeout"))

    health = authentication_health()
    assert health["provider_status"] == "degraded"
    assert health["provider_kind"] == "supabase"
    assert health["provider_error"] == "timeout"
    assert "secret-provider" not in json.dumps(health)


def test_provider_failure_categories_are_bounded(monkeypatch):
    cases = [
        (HTTPError("https://secret.example/jwks", 404, "missing", {}, None), "http_404"),
        (URLError(socket.gaierror(-2, "secret DNS failure")), "dns_error"),
        (URLError(ssl.SSLError("secret TLS failure")), "tls_error"),
        (json.JSONDecodeError("secret invalid payload", "x", 0), "invalid_json"),
        (ValueError("secret malformed key"), "invalid_jwks"),
    ]

    for exc, expected in cases:
        verifier = _configured_provider(monkeypatch)
        _force_failure(verifier, monkeypatch, exc)
        health = authentication_health()
        assert health["provider_error"] == expected
        serialized = json.dumps(health)
        assert "secret" not in serialized
        _reset_verifier()


def test_non_supabase_provider_kind_is_reported_without_url(monkeypatch):
    _configured_provider(monkeypatch, issuer="https://identity.example.test/issuer")
    health = authentication_health()

    assert health["provider_kind"] == "oidc"
    assert "identity.example" not in json.dumps(health)
