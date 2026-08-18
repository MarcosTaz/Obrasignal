import pytest


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
