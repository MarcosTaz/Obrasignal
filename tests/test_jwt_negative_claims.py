import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from auth_context_jwt import JwtVerifier


ISSUER = "https://claims.example/auth/v1"


def _verifier_and_key():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "claims-key", "use": "sig", "alg": "RS256"})
    verifier = JwtVerifier(ISSUER)
    verifier._key_for = lambda kid: jwk
    return verifier, private_key


def _token(private_key, claims):
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "claims-key"},
    )


def _valid_claims():
    now = int(time.time())
    return {
        "sub": "claims-user",
        "iss": ISSUER,
        "aud": "authenticated",
        "iat": now,
        "exp": now + 300,
    }


def test_jwt_verifier_rejects_wrong_issuer():
    verifier, private_key = _verifier_and_key()
    claims = _valid_claims()
    claims["iss"] = "https://wrong.example/auth/v1"

    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(_token(private_key, claims))


def test_jwt_verifier_rejects_expired_token():
    verifier, private_key = _verifier_and_key()
    claims = _valid_claims()
    claims["iat"] = int(time.time()) - 600
    claims["exp"] = int(time.time()) - 300

    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(_token(private_key, claims))


def test_jwt_verifier_rejects_missing_subject():
    verifier, private_key = _verifier_and_key()
    claims = _valid_claims()
    claims.pop("sub")

    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(_token(private_key, claims))
