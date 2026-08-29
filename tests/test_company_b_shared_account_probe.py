import json
import time

import jwt
import pytest

from auth_context_jwt import JwtVerifier


def _signing_material():
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "company-b-key", "use": "sig", "alg": "RS256"})
    return private_key, jwk


def _token(private_key, subject, *, account_id, role):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": subject,
            "iss": "https://issuer.example",
            "aud": "authenticated",
            "iat": now - 10,
            "exp": now + 3600,
            # Supabase app_metadata is server-controlled; unlike user_metadata it
            # is suitable for trusted tenant/role assignment when configured by
            # the operator. The verifier must never accept equivalent values from
            # user_metadata.
            "app_metadata": {
                "obrasignal_account_id": account_id,
                "obrasignal_role": role,
            },
            "user_metadata": {
                "obrasignal_account_id": "attacker-controlled-account",
                "obrasignal_role": "owner",
            },
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "company-b-key"},
    )


def test_company_b_two_verified_subjects_can_share_one_trusted_company_account():
    private_key, jwk = _signing_material()
    verifier = JwtVerifier(
        "https://issuer.example",
        bootstrap_json=json.dumps({"keys": [jwk]}),
    )

    owner = verifier.verify(
        _token(private_key, "company-b-owner-user", account_id="company-b", role="owner")
    )
    member = verifier.verify(
        _token(private_key, "company-b-member-user", account_id="company-b", role="member")
    )

    assert owner.subject == "company-b-owner-user"
    assert member.subject == "company-b-member-user"
    assert owner.account_id == "company-b"
    assert member.account_id == "company-b"
    assert owner.claims["app_metadata"]["obrasignal_role"] == "owner"
    assert member.claims["app_metadata"]["obrasignal_role"] == "member"


def test_company_b_user_metadata_cannot_select_tenant_when_trusted_mapping_absent():
    private_key, jwk = _signing_material()
    verifier = JwtVerifier(
        "https://issuer.example",
        bootstrap_json=json.dumps({"keys": [jwk]}),
    )
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "company-b-unmapped-user",
            "iss": "https://issuer.example",
            "aud": "authenticated",
            "iat": now - 10,
            "exp": now + 3600,
            "user_metadata": {
                "obrasignal_account_id": "attacker-controlled-account",
                "obrasignal_role": "owner",
            },
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "company-b-key"},
    )

    identity = verifier.verify(token)
    assert identity.subject == "company-b-unmapped-user"
    assert identity.account_id == "company-b-unmapped-user"
