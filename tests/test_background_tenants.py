"""Background sync must not create implicit customer identities in production."""
import pytest

import account_registry
import auth_context
from background_tenants import eligible_background_accounts


def test_provider_with_no_active_accounts_is_clean_noop(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setattr(account_registry, "list_active_accounts", lambda conn: [])
    def forbidden_identity():
        raise AssertionError("background worker must not request a Flask identity")
    monkeypatch.setattr(auth_context, "configured_identity", forbidden_identity)
    assert eligible_background_accounts(object()) == []


def test_provider_uses_only_existing_active_accounts(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setattr(
        account_registry, "list_active_accounts", lambda conn: ["tenant-A", "tenant-B"]
    )
    monkeypatch.setattr(
        auth_context, "configured_identity",
        lambda: (_ for _ in ()).throw(AssertionError("implicit identity forbidden"))
    )
    assert eligible_background_accounts(object()) == ["tenant-A", "tenant-B"]


def test_provider_accepts_known_active_list_without_refetch(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setattr(
        account_registry, "list_active_accounts",
        lambda conn: (_ for _ in ()).throw(AssertionError("unexpected second query")),
    )
    assert eligible_background_accounts(object(), existing_accounts=["active-A"]) == ["active-A"]


def test_development_preserves_explicit_demo_fallback(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setattr(account_registry, "list_active_accounts", lambda conn: [])
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "demo")
    assert eligible_background_accounts(object()) == ["demo"]


def test_invalid_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "incorrect")
    monkeypatch.setattr(account_registry, "list_active_accounts", lambda conn: [])
    with pytest.raises(RuntimeError, match="Invalid OBRASIGNAL_AUTH_MODE"):
        eligible_background_accounts(object())
