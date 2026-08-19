import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture()
def clear_auth_env(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)


def test_development_identity_is_not_authenticated(clear_auth_env):
    from auth_context import configured_identity

    identity = configured_identity()
    assert identity.account_id == "default"
    assert identity.authenticated is False


def test_development_identity_uses_configured_account(clear_auth_env, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "empresa-1")

    from auth_context import configured_identity

    identity = configured_identity()
    assert identity.account_id == "empresa-1"
    assert identity.authenticated is False


def test_provider_mode_without_real_provider_fails(clear_auth_env, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "empresa-1")

    from auth_context import configured_identity

    with pytest.raises(RuntimeError, match="provider is not configured"):
        configured_identity()


def test_unknown_auth_mode_fails(clear_auth_env, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "anything")

    from auth_context import configured_identity

    with pytest.raises(RuntimeError, match="Invalid OBRASIGNAL_AUTH_MODE"):
        configured_identity()


def test_invalid_account_id_fails(clear_auth_env, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "../other-account")

    from auth_context import configured_identity

    with pytest.raises(RuntimeError, match="Invalid OBRASIGNAL_ACCOUNT_ID"):
        configured_identity()


def _signed_test_token(private_key, *, issuer="https://example.supabase.co", audience="authenticated"):
    now = int(time.time())
    return jwt.encode(
        {"sub": "user-123", "iss": issuer, "aud": audience, "iat": now, "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def test_supabase_project_url_is_normalized_to_auth_issuer():
    from auth_context_jwt import JwtVerifier

    verifier = JwtVerifier("https://example.supabase.co")

    assert verifier.issuer == "https://example.supabase.co/auth/v1"
    assert verifier.jwks_url == "https://example.supabase.co/auth/v1/.well-known/jwks.json"


def test_existing_supabase_auth_issuer_is_preserved():
    from auth_context_jwt import JwtVerifier

    verifier = JwtVerifier("https://example.supabase.co/auth/v1")

    assert verifier.issuer == "https://example.supabase.co/auth/v1"
    assert verifier.jwks_url == "https://example.supabase.co/auth/v1/.well-known/jwks.json"


def test_jwt_verifier_accepts_valid_rs256_token():
    from auth_context_jwt import JwtVerifier

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))

    verifier = JwtVerifier("https://example.supabase.co/auth/v1")
    verifier._jwks = lambda: {"test-key": jwk}

    identity = verifier.verify(_signed_test_token(private_key, issuer="https://example.supabase.co/auth/v1"))

    assert identity.account_id == "user-123"
    assert identity.subject == "user-123"
    assert identity.claims["aud"] == "authenticated"


def test_jwt_verifier_rejects_wrong_audience():
    from auth_context_jwt import JwtVerifier

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))

    verifier = JwtVerifier("https://example.supabase.co/auth/v1")
    verifier._jwks = lambda: {"test-key": jwk}

    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(_signed_test_token(private_key, issuer="https://example.supabase.co/auth/v1", audience="wrong-audience"))
