import json
import time

import jwt
import pytest

import auth_context_jwt
from auth_context_jwt import JwtVerifier, _normalize_supabase_issuer


@pytest.mark.parametrize(
    "configured",
    [
        "https://project-ref.supabase.co",
        "https://project-ref.supabase.co/",
        "https://project-ref.supabase.co/rest/v1",
        "https://project-ref.supabase.co/rest/v1/",
        "https://project-ref.supabase.co/auth/v1",
        "https://project-ref.supabase.co/auth/v1/",
        "https://project-ref.supabase.co/some/obsolete/path",
    ],
)
def test_native_supabase_project_urls_normalize_to_canonical_auth_issuer(configured):
    assert _normalize_supabase_issuer(configured) == "https://project-ref.supabase.co/auth/v1"


def test_non_supabase_oidc_issuer_is_not_rewritten():
    issuer = "https://identity.example.com/tenant/v2"
    assert _normalize_supabase_issuer(issuer) == issuer


def test_native_supabase_ignores_stale_explicit_jwks_override():
    verifier = JwtVerifier(
        "https://project-ref.supabase.co/rest/v1",
        jwks_url="https://legacy-keys.example.invalid/old.json",
    )
    assert verifier.issuer == "https://project-ref.supabase.co/auth/v1"
    assert verifier.jwks_url == (
        "https://project-ref.supabase.co/auth/v1/.well-known/jwks.json"
    )


def test_non_supabase_oidc_keeps_explicit_jwks_override():
    verifier = JwtVerifier(
        "https://identity.example.com/tenant",
        jwks_url="https://keys.example.com/jwks.json",
    )
    assert verifier.jwks_url == "https://keys.example.com/jwks.json"


def test_production_verifier_canonicalizes_rest_url_and_ignores_stale_supabase_jwks(
    monkeypatch,
):
    monkeypatch.setenv(
        "OBRASIGNAL_JWT_ISSUER",
        "https://project-ref.supabase.co/rest/v1",
    )
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv(
        "OBRASIGNAL_JWKS_URL",
        "https://stale.example.invalid/keys.json",
    )
    monkeypatch.setattr(auth_context_jwt, "_verifier", None)
    monkeypatch.setattr(auth_context_jwt, "_verifier_config", None)

    verifier = auth_context_jwt.production_verifier()

    assert verifier.issuer == "https://project-ref.supabase.co/auth/v1"
    assert verifier.jwks_url == (
        "https://project-ref.supabase.co/auth/v1/.well-known/jwks.json"
    )


def test_es256_supabase_shape_verifies_with_public_ec_jwk(monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "supabase-es256", "use": "sig", "alg": "ES256"})

    issuer = "https://project-ref.supabase.co/auth/v1"
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "d1e41e41-2d3d-4fb5-8e96-b7505b89d314",
            "iss": issuer,
            "aud": "authenticated",
            "iat": now - 5,
            "exp": now + 300,
            "role": "authenticated",
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "supabase-es256", "typ": "JWT"},
    )

    verifier = JwtVerifier(issuer)
    monkeypatch.setattr(verifier, "_key_for", lambda kid: jwk)

    identity = verifier.verify(token)

    assert identity.account_id == "d1e41e41-2d3d-4fb5-8e96-b7505b89d314"
    assert identity.subject == identity.account_id
    assert identity.claims["aud"] == "authenticated"
    assert identity.claims["role"] == "authenticated"


def test_token_algorithm_must_match_jwk_algorithm(monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "key-1", "use": "sig", "alg": "RS256"})

    issuer = "https://project-ref.supabase.co/auth/v1"
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": issuer,
            "aud": "authenticated",
            "iat": now - 5,
            "exp": now + 300,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "key-1"},
    )

    verifier = JwtVerifier(issuer)
    monkeypatch.setattr(verifier, "_key_for", lambda kid: jwk)

    with pytest.raises(jwt.InvalidTokenError, match="algorithm"):
        verifier.verify(token)
