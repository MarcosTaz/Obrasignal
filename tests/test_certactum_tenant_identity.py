from __future__ import annotations

import pytest
from jwt import InvalidTokenError

from auth_context import _verified_tenant_id


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
