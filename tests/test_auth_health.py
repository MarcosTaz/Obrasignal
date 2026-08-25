import auth_context_jwt as auth_jwt
from auth_context_jwt import JwksUnavailableError, authentication_health, production_verifier


def _reset_verifier():
    auth_jwt._verifier = None
    auth_jwt._verifier_config = None


def test_authentication_health_reports_missing_provider_config(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.delenv("OBRASIGNAL_JWT_ISSUER", raising=False)
    monkeypatch.delenv("OBRASIGNAL_JWT_AUDIENCE", raising=False)
    _reset_verifier()

    assert authentication_health() == {
        "mode": "provider",
        "config_present": False,
        "provider_status": "misconfigured",
    }


def test_authentication_health_is_passive_before_first_jwks_fetch(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://project-a.supabase.co")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    _reset_verifier()

    assert authentication_health() == {
        "mode": "provider",
        "config_present": True,
        "provider_status": "uninitialized",
    }


def test_authentication_health_reports_ready_after_successful_key_refresh(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://project-a.supabase.co")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    _reset_verifier()
    verifier = production_verifier()
    monkeypatch.setattr(verifier, "_fetch_jwks", lambda: {"known": {"kid": "known"}})

    assert verifier._key_for("known")["kid"] == "known"
    assert authentication_health()["provider_status"] == "ready"


def test_authentication_health_reports_degraded_after_provider_failure(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://project-a.supabase.co")
    monkeypatch.setenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated")
    _reset_verifier()
    verifier = production_verifier()
    monkeypatch.setattr(
        verifier,
        "_fetch_jwks",
        lambda: (_ for _ in ()).throw(TimeoutError("provider timeout")),
    )

    try:
        verifier._key_for("unknown")
    except JwksUnavailableError:
        pass
    else:
        raise AssertionError("provider failure must fail closed")

    assert authentication_health()["provider_status"] == "degraded"
