import base64
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import jwt
from flask import Flask

import auth_context
import auth_context_jwt
from auth_context_jwt import JwksUnavailableError, JwtVerifier


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture()
def signing_material():
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
    return private_key, jwk


def _token(private_key, *, kid="test-key", issuer="https://issuer.example", audience="authenticated", expires=3600):
    now = int(time.time())
    return jwt.encode(
        {"sub": "user-123", "iss": issuer, "aud": audience, "iat": now - 10, "exp": now + expires},
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def test_provider_mode_requires_bearer_token(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://example.supabase.co/auth/v1")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv("OBRASIGNAL_JWKS_URL", "https://example.invalid/keys")
    app = Flask(__name__)

    with app.test_request_context("/api", headers={}):
        with pytest.raises(Exception, match="Bearer token required"):
            auth_context.configured_identity()


def test_jwt_verifier_uses_verified_sub(monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(public.n.to_bytes((public.n.bit_length() + 7) // 8, "big")),
        "e": _b64url(public.e.to_bytes((public.e.bit_length() + 7) // 8, "big")),
    }

    verifier = JwtVerifier(
        issuer="https://issuer.example",
        audience="authenticated",
        jwks_url="https://keys.example/jwks",
        cache_seconds=300,
    )
    monkeypatch.setattr(verifier, "_key_for", lambda kid: jwk)

    import jwt

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": "https://issuer.example",
            "aud": "authenticated",
            "iat": now - 10,
            "exp": now + 3600,
        },
        key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    identity = verifier.verify(token)
    assert identity.account_id == "user-123"
    assert identity.subject == "user-123"
    assert identity.claims["aud"] == "authenticated"


def test_production_verifier_reuses_jwks_cache(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://cache.supabase.co")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.delenv("OBRASIGNAL_JWKS_URL", raising=False)
    monkeypatch.setattr(auth_context_jwt, "_verifier", None)
    monkeypatch.setattr(auth_context_jwt, "_verifier_config", None)

    first = auth_context_jwt.production_verifier()
    second = auth_context_jwt.production_verifier()

    assert second is first
    assert first.issuer == "https://cache.supabase.co/auth/v1"


def test_jwks_first_verify_fetches_and_warm_cache_does_not(signing_material, monkeypatch):
    private_key, jwk = signing_material
    verifier = JwtVerifier("https://issuer.example")
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        return {"test-key": jwk}

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)
    token = _token(private_key)

    assert verifier.verify(token).subject == "user-123"
    assert verifier.verify(token).subject == "user-123"
    assert calls == 1


def test_expired_cache_uses_stale_key_when_refresh_times_out(signing_material, monkeypatch):
    private_key, jwk = signing_material
    verifier = JwtVerifier("https://issuer.example")
    verifier._keys = {"test-key": jwk}
    verifier._expires_at = 0
    verifier._fetched_at = time.time() - 300
    monkeypatch.setattr(verifier, "_fetch_jwks", lambda: (_ for _ in ()).throw(TimeoutError("timed out")))

    assert verifier.verify(_token(private_key)).subject == "user-123"


def test_expired_cache_rejects_key_beyond_stale_limit(signing_material, monkeypatch):
    private_key, jwk = signing_material
    verifier = JwtVerifier("https://issuer.example", stale_max_seconds=3600)
    verifier._keys = {"test-key": jwk}
    verifier._expires_at = 0
    verifier._fetched_at = time.time() - 3601
    monkeypatch.setattr(verifier, "_fetch_jwks", lambda: (_ for _ in ()).throw(TimeoutError("timed out")))

    with pytest.raises(JwksUnavailableError):
        verifier.verify(_token(private_key))


def test_empty_cache_timeout_is_controlled_unavailable(signing_material, monkeypatch):
    private_key, _ = signing_material
    verifier = JwtVerifier("https://issuer.example")
    monkeypatch.setattr(verifier, "_fetch_jwks", lambda: (_ for _ in ()).throw(TimeoutError("timed out")))

    with pytest.raises(JwksUnavailableError):
        verifier.verify(_token(private_key))


def test_unknown_kid_refreshes_exactly_once_then_rejects(signing_material, monkeypatch):
    private_key, jwk = signing_material
    verifier = JwtVerifier("https://issuer.example")
    verifier._keys = {"test-key": jwk}
    verifier._expires_at = time.time() + 300
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        return {"test-key": jwk}

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)
    with pytest.raises(jwt.InvalidTokenError, match="unknown JWT key id"):
        verifier.verify(_token(private_key, kid="rotated-key"))
    assert calls == 1


def test_invalid_signature_and_registered_claims_remain_enforced(signing_material, monkeypatch):
    private_key, jwk = signing_material
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = JwtVerifier("https://issuer.example")
    monkeypatch.setattr(verifier, "_fetch_jwks", lambda: {"test-key": jwk})

    with pytest.raises(jwt.InvalidSignatureError):
        verifier.verify(_token(other_key))
    with pytest.raises(jwt.InvalidIssuerError):
        verifier.verify(_token(private_key, issuer="https://wrong.example"))
    with pytest.raises(jwt.InvalidAudienceError):
        verifier.verify(_token(private_key, audience="wrong"))
    with pytest.raises(jwt.ExpiredSignatureError):
        verifier.verify(_token(private_key, expires=-1))


def test_concurrent_cold_cache_uses_single_fetch(signing_material, monkeypatch):
    private_key, jwk = signing_material
    verifier = JwtVerifier("https://issuer.example")
    token = _token(private_key)
    calls = 0
    fetch_started = threading.Event()
    release_fetch = threading.Event()

    def fetch():
        nonlocal calls
        calls += 1
        fetch_started.set()
        assert release_fetch.wait(timeout=2)
        return {"test-key": jwk}

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(verifier.verify, token) for _ in range(8)]
        assert fetch_started.wait(timeout=2)
        release_fetch.set()
        assert [future.result().subject for future in futures] == ["user-123"] * 8
    assert calls == 1


def test_concurrent_expired_stale_cache_failure_uses_single_fetch(signing_material, monkeypatch):
    private_key, jwk = signing_material
    verifier = JwtVerifier("https://issuer.example")
    verifier._keys = {"test-key": jwk}
    verifier._expires_at = 0
    verifier._fetched_at = time.time() - 300
    token = _token(private_key)
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(verifier, "_fetch_jwks", fetch)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert [identity.subject for identity in pool.map(verifier.verify, [token] * 8)] == ["user-123"] * 8
    assert calls == 1
