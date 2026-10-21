from types import SimpleNamespace

import pytest

from factories.capacity_commitment import auth


def test_provider_tenant_resolver_accepts_authenticated_identity(monkeypatch):
    monkeypatch.setattr(
        auth,
        "configured_identity",
        lambda: SimpleNamespace(account_id="tenant-a", authenticated=True),
    )
    assert auth.provider_tenant_resolver(object()) == "tenant-a"


def test_provider_tenant_resolver_rejects_development_identity(monkeypatch):
    monkeypatch.setattr(
        auth,
        "configured_identity",
        lambda: SimpleNamespace(account_id="default", authenticated=False),
    )
    assert auth.provider_tenant_resolver(object()) is None


def test_provider_tenant_resolver_rejects_blank_authenticated_account(monkeypatch):
    monkeypatch.setattr(
        auth,
        "configured_identity",
        lambda: SimpleNamespace(account_id=" ", authenticated=True),
    )
    assert auth.provider_tenant_resolver(object()) is None


def test_provider_tenant_resolver_does_not_swallow_verifier_failure(monkeypatch):
    def fail():
        raise RuntimeError("provider failure")

    monkeypatch.setattr(auth, "configured_identity", fail)
    with pytest.raises(RuntimeError, match="provider failure"):
        auth.provider_tenant_resolver(object())
