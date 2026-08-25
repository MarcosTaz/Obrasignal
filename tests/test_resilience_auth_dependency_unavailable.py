"""Defensive resilience probes for the local JWT/JWKS dependency boundary.

Test-only: no network calls, no provider access, no runtime wiring.
"""

import time

import pytest

from auth_context_jwt import JwksUnavailableError, JwtVerifier


ISSUER = "https://example.invalid/auth/v1"


def verifier(*, stale_max_seconds=60):
    return JwtVerifier(
        issuer=ISSUER,
        audience="authenticated",
        jwks_url="https://example.invalid/auth/v1/.well-known/jwks.json",
        cache_seconds=30,
        stale_max_seconds=stale_max_seconds,
    )


def test_jwks_unavailable_without_cached_key_fails_closed_and_stays_retryable(monkeypatch):
    v = verifier(stale_max_seconds=0)
    monkeypatch.setattr(v, "_fetch_jwks", lambda: (_ for _ in ()).throw(TimeoutError("controlled")))

    with pytest.raises(JwksUnavailableError):
        v._key_for("kid-a")

    diagnostics = v.provider_diagnostics()
    assert diagnostics["provider_status"] == "degraded"
    assert diagnostics["provider_error"] == "timeout"
    assert v._retry_at > time.time()
    assert v._keys is None


def test_unavailable_refresh_may_use_bounded_stale_key_but_health_remains_degraded(monkeypatch):
    v = verifier(stale_max_seconds=120)
    now = time.time()
    v._keys = {"kid-a": {"kid": "kid-a"}}
    v._fetched_at = now - 40
    v._expires_at = now - 1
    monkeypatch.setattr(v, "_fetch_jwks", lambda: (_ for _ in ()).throw(TimeoutError("controlled")))

    assert v._key_for("kid-a")["kid"] == "kid-a"
    assert v.provider_diagnostics()["provider_status"] == "degraded"


def test_malformed_jwks_is_dependency_failure_not_authenticated_fallback(monkeypatch):
    v = verifier(stale_max_seconds=0)
    monkeypatch.setattr(v, "_fetch_jwks", lambda: (_ for _ in ()).throw(ValueError("controlled malformed response")))

    with pytest.raises(JwksUnavailableError):
        v._key_for("kid-a")

    diagnostics = v.provider_diagnostics()
    assert diagnostics["provider_status"] == "degraded"
    assert diagnostics["provider_error"] == "invalid_jwks"
    assert v._keys is None


def test_provider_response_recovery_clears_degraded_only_after_successful_key_refresh(monkeypatch):
    v = verifier(stale_max_seconds=0)
    monkeypatch.setattr(v, "_fetch_jwks", lambda: (_ for _ in ()).throw(TimeoutError("controlled")))
    with pytest.raises(JwksUnavailableError):
        v._key_for("kid-a")
    assert v.provider_diagnostics()["provider_status"] == "degraded"

    v._retry_at = 0.0
    monkeypatch.setattr(v, "_fetch_jwks", lambda: {"kid-a": {"kid": "kid-a"}})
    assert v._key_for("kid-a")["kid"] == "kid-a"
    assert v.provider_diagnostics() == {
        "provider_status": "ready",
        "provider_kind": "oidc",
        "provider_error": None,
    }


def test_unknown_key_after_successful_refresh_is_invalid_token_semantics_not_dependency_unavailable(monkeypatch):
    from jwt import InvalidTokenError

    v = verifier(stale_max_seconds=0)
    monkeypatch.setattr(v, "_fetch_jwks", lambda: {"kid-known": {"kid": "kid-known"}})

    with pytest.raises(InvalidTokenError, match="unknown JWT key id"):
        v._key_for("kid-unknown")

    assert v.provider_diagnostics()["provider_status"] == "ready"
