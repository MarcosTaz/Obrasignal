from __future__ import annotations

import pytest
from jwt import InvalidTokenError

from auth_context import _enforce_mfa_assurance, _verified_tenant_id


def test_default_tenant_identity_remains_subject_for_compatibility(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_JWT_TENANT_CLAIM", raising=False)
    assert _verified_tenant_id({"sub": "user-a"}, "user-a") == "user-a"


def test_provider_managed_nested_tenant_claim_separates_user_from_company(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_JWT_TENANT_CLAIM", "app_metadata.tenant_id")
    claims = {
        "sub": "user-a",
        "app_metadata": {"tenant_id": "company-123", "roles": ["operator"]},
        "user_metadata": {"tenant_id": "attacker-controlled-value"},
    }
    assert _verified_tenant_id(claims, "user-a") == "company-123"


def test_missing_verified_tenant_claim_fails_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_JWT_TENANT_CLAIM", "app_metadata.tenant_id")
    with pytest.raises(InvalidTokenError, match="tenant claim is missing"):
        _verified_tenant_id({"sub": "user-a", "app_metadata": {}}, "user-a")


def test_non_scalar_verified_tenant_claim_fails_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_JWT_TENANT_CLAIM", "app_metadata.tenant_id")
    with pytest.raises(InvalidTokenError, match="scalar identifier"):
        _verified_tenant_id({"app_metadata": {"tenant_id": ["company-a", "company-b"]}}, "user-a")


def test_mfa_gate_is_backward_compatible_until_explicitly_enabled(monkeypatch):
    monkeypatch.delenv("CERTACTUM_REQUIRE_MFA", raising=False)
    _enforce_mfa_assurance({"sub": "user-a", "aal": "aal1"})


def test_mfa_gate_accepts_only_signed_aal2_when_enabled(monkeypatch):
    monkeypatch.setenv("CERTACTUM_REQUIRE_MFA", "true")
    _enforce_mfa_assurance({"sub": "user-a", "aal": "aal2"})


@pytest.mark.parametrize("claims", [{"sub": "user-a"}, {"sub": "user-a", "aal": "aal1"}, {"sub": "user-a", "aal": 2}])
def test_mfa_gate_fails_closed_without_aal2(monkeypatch, claims):
    monkeypatch.setenv("CERTACTUM_REQUIRE_MFA", "true")
    with pytest.raises(InvalidTokenError, match="mfa assurance level is insufficient"):
        _enforce_mfa_assurance(claims)


def test_mfa_gate_rejects_invalid_operator_configuration(monkeypatch):
    monkeypatch.setenv("CERTACTUM_REQUIRE_MFA", "sometimes")
    with pytest.raises(RuntimeError, match="CERTACTUM_REQUIRE_MFA is invalid"):
        _enforce_mfa_assurance({"aal": "aal2"})
