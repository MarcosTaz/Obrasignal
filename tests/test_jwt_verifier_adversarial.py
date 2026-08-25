import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from auth_context_jwt import JwksUnavailableError, JwtVerifier


def _rsa_material(*, kid="test-key", alg="RS256"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": alg})
    return private_key, jwk


def _token(private_key, *, kid="test-key", issuer="https://project-a.supabase.co/auth/v1",
           audience="authenticated", issued_at=None, expires_at=None):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "user-123",
            "iss": issuer,
            "aud": audience,
            "iat": now if issued_at is None else issued_at,
            "exp": now + 300 if expires_at is None else expires_at,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid, "typ": "JWT"},
    )


def test_rejects_validly_signed_token_from_other_supabase_project(monkeypatch):
    private_key, jwk = _rsa_material()
    verifier = JwtVerifier("https://project-a.supabase.co")
    monkeypatch.setattr(verifier, "_key_for", lambda _kid: jwk)

    token = _token(private_key, issuer="https://project-b.supabase.co/auth/v1")

    with pytest.raises(jwt.InvalidIssuerError):
        verifier.verify(token)


def test_rejects_wrong_audience(monkeypatch):
    private_key, jwk = _rsa_material()
    verifier = JwtVerifier("https://project-a.supabase.co")
    monkeypatch.setattr(verifier, "_key_for", lambda _kid: jwk)

    with pytest.raises(jwt.InvalidAudienceError):
        verifier.verify(_token(private_key, audience="another-audience"))


def test_rejects_expired_token(monkeypatch):
    private_key, jwk = _rsa_material()
    verifier = JwtVerifier("https://project-a.supabase.co")
    monkeypatch.setattr(verifier, "_key_for", lambda _kid: jwk)
    now = int(time.time())

    with pytest.raises(jwt.ExpiredSignatureError):
        verifier.verify(_token(private_key, issued_at=now - 600, expires_at=now - 1))


def test_rejects_token_issued_unacceptably_in_future(monkeypatch):
    private_key, jwk = _rsa_material()
    verifier = JwtVerifier("https://project-a.supabase.co")
    monkeypatch.setattr(verifier, "_key_for", lambda _kid: jwk)
    now = int(time.time())

    with pytest.raises(jwt.ImmatureSignatureError):
        verifier.verify(_token(private_key, issued_at=now + 600, expires_at=now + 900))


def test_rejects_hs256_before_any_jwks_lookup(monkeypatch):
    verifier = JwtVerifier("https://project-a.supabase.co")
    monkeypatch.setattr(
        verifier,
        "_key_for",
        lambda _kid: (_ for _ in ()).throw(AssertionError("JWKS lookup must not run")),
    )
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": "https://project-a.supabase.co/auth/v1",
            "aud": "authenticated",
            "iat": now,
            "exp": now + 300,
        },
        "shared-secret-used-only-for-hs256-rejection-test",
        algorithm="HS256",
        headers={"kid": "symmetric-key"},
    )

    with pytest.raises(jwt.InvalidTokenError, match="unsupported JWT header"):
        verifier.verify(token)


def test_unknown_kid_fails_closed_after_one_refresh(monkeypatch):
    _private_key, jwk = _rsa_material(kid="known-key")
    verifier = JwtVerifier("https://project-a.supabase.co")
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        return {"known-key": jwk}

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)

    with pytest.raises(jwt.InvalidTokenError, match="unknown JWT key id"):
        verifier._key_for("unknown-key")
    assert calls == 1


def test_cold_cache_refresh_is_single_flight_under_concurrency(monkeypatch):
    _private_key, jwk = _rsa_material(kid="cold-key")
    verifier = JwtVerifier("https://project-a.supabase.co")
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return {"cold-key": jwk}

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _index: verifier._key_for("cold-key"), range(8)))

    assert all(result["kid"] == "cold-key" for result in results)
    assert calls == 1


def test_provider_outage_is_single_flight_and_returns_service_unavailable(monkeypatch):
    verifier = JwtVerifier("https://project-a.supabase.co")
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)

    def attempt(_index):
        with pytest.raises(JwksUnavailableError):
            verifier._key_for("missing-key")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(attempt, range(8)))

    assert calls == 1


def test_recent_stale_key_can_verify_during_temporary_provider_outage(monkeypatch):
    private_key, jwk = _rsa_material(kid="stale-key")
    verifier = JwtVerifier(
        "https://project-a.supabase.co",
        cache_seconds=30,
        stale_max_seconds=3600,
    )
    verifier._keys = {"stale-key": jwk}
    verifier._fetched_at = time.time() - 60
    verifier._expires_at = time.time() - 1
    monkeypatch.setattr(
        verifier,
        "_fetch_jwks",
        lambda: (_ for _ in ()).throw(TimeoutError("provider timed out")),
    )

    identity = verifier.verify(_token(private_key, kid="stale-key"))

    assert identity.account_id == "user-123"


def test_too_old_stale_key_does_not_mask_provider_outage(monkeypatch):
    _private_key, jwk = _rsa_material(kid="stale-key")
    verifier = JwtVerifier(
        "https://project-a.supabase.co",
        cache_seconds=30,
        stale_max_seconds=60,
    )
    verifier._keys = {"stale-key": jwk}
    verifier._fetched_at = time.time() - 120
    verifier._expires_at = time.time() - 90
    monkeypatch.setattr(
        verifier,
        "_fetch_jwks",
        lambda: (_ for _ in ()).throw(TimeoutError("provider timed out")),
    )

    with pytest.raises(JwksUnavailableError):
        verifier._key_for("stale-key")


def test_q080_integration_preserves_native_jwks_and_disabled_evidence_defaults():
    """Integration-only guard for the Auth/render semantic union and live-gate trigger."""
    render = (Path(__file__).resolve().parents[1] / "render.yaml").read_text(encoding="utf-8")
    assert "OBRASIGNAL_JWT_ISSUER" in render
    assert "OBRASIGNAL_JWKS_URL" not in render
    assert '- key: OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1\n        value: "false"' in render
    assert '- key: OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1\n        value: "false"' in render
