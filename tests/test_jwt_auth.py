import base64
import time

import pytest
from flask import Flask

import auth_context
from auth_context_jwt import JwtVerifier


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


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
    monkeypatch.setattr(verifier, "_jwks", lambda: {"test-key": jwk})

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
