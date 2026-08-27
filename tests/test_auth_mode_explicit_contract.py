import pytest

import api
from auth_context_jwt import authentication_health


def test_missing_auth_mode_is_misconfigured_not_development(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)

    assert authentication_health() == {
        "mode": "missing",
        "config_present": False,
        "provider_status": "misconfigured",
    }


def test_empty_auth_mode_is_misconfigured_not_development(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "   ")

    assert authentication_health() == {
        "mode": "missing",
        "config_present": False,
        "provider_status": "misconfigured",
    }


def test_explicit_development_mode_remains_available(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")

    assert authentication_health() == {
        "mode": "development",
        "config_present": True,
        "provider_status": "not_applicable",
    }


def test_provider_mode_without_issuer_remains_fail_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.delenv("OBRASIGNAL_JWT_ISSUER", raising=False)

    assert authentication_health() == {
        "mode": "provider",
        "config_present": False,
        "provider_status": "misconfigured",
    }


def test_missing_auth_mode_cannot_enable_development_cors(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "*")

    with pytest.raises(RuntimeError, match="OBRASIGNAL_AUTH_MODE must be explicitly configured"):
        api._cors_origin()


def test_explicit_development_mode_can_keep_development_cors(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_CORS_ORIGIN", "*")

    assert api._cors_origin() == "*"
