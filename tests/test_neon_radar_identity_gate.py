"""The existing Radar API identity boundary must stay disabled by default."""
from types import SimpleNamespace
from flask import Flask
import api

def test_neon_radar_company_gate_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_NEON_COMPANY_AUTH", raising=False)
    identity = SimpleNamespace(account_id="legacy-account", authenticated=True)
    monkeypatch.setattr(api, "configured_identity", lambda: identity)
    assert api._identity() is identity

def test_neon_radar_company_gate_denies_untrusted_issuer(monkeypatch):
    from jwt import InvalidTokenError
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "staging")
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_NEON_STAGING_ISSUER", "https://trusted-neon")
    monkeypatch.setattr(api, "configured_identity", lambda: SimpleNamespace(
        authenticated=True, subject="11111111-1111-4111-8111-111111111111",
        claims={"iss":"https://other-provider"}, account_id="old-account"))
    app = Flask(__name__)
    with app.test_request_context("/", headers={
        "X-ObraSignal-Company-ID": "22222222-2222-4222-8222-222222222222"}):
        try:
            api._identity()
        except InvalidTokenError:
            return
        raise AssertionError("untrusted provider accepted")


def test_unknown_neon_mode_fails_closed(monkeypatch):
    from jwt import InvalidTokenError
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "stagng")
    identity = SimpleNamespace(account_id="legacy-account", authenticated=True)
    monkeypatch.setattr(api, "configured_identity", lambda: identity)
    try:
        api._identity()
    except RuntimeError as exc:
        assert "OBRASIGNAL_NEON_COMPANY_AUTH" in str(exc)
    else:
        raise AssertionError("misspelled Neon mode silently bypassed tenant authorization")


def test_development_auth_forbidden_on_production_hosts(monkeypatch):
    from auth_context import configured_identity
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("OBRASIGNAL_ENV", raising=False)
    try:
        configured_identity()
    except RuntimeError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("unauthenticated development identity accepted on Render")

    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("OBRASIGNAL_ENV", "production")
    try:
        configured_identity()
    except RuntimeError:
        pass
    else:
        raise AssertionError("unauthenticated development identity accepted in production")


def test_development_identity_still_available_locally(monkeypatch):
    from auth_context import configured_identity
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ENV", "test")
    monkeypatch.delenv("RENDER", raising=False)
    identity = configured_identity()
    assert identity.authenticated is False


def test_development_auth_rejected_on_supported_cloud_hosts(monkeypatch):
    import pytest
    from auth_context import configured_identity

    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ENV", "test")
    monkeypatch.delenv("RENDER", raising=False)
    for variable in ("RENDER_EXTERNAL_HOSTNAME", "RENDER_SERVICE_ID", "VERCEL", "K_SERVICE", "DYNO"):
        with monkeypatch.context() as hosted:
            hosted.setenv(variable, "synthetic-host-value")
            with pytest.raises(RuntimeError, match="forbidden"):
                configured_identity()


def test_neon_gate_requires_provider_mode_even_with_verified_identity_stub(monkeypatch):
    import pytest
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "staging")
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setattr(api, "configured_identity", lambda: SimpleNamespace(
        account_id="untrusted", authenticated=True,
        subject="11111111-1111-4111-8111-111111111111", claims={"iss": "neon-test"}
    ))
    with pytest.raises(RuntimeError, match="requires provider"):
        api._identity()


def test_obrasignal_mfa_policy_is_independent_of_certactum(monkeypatch):
    import pytest
    from jwt import InvalidTokenError
    from auth_context import _mfa_required, _enforce_mfa_assurance

    monkeypatch.setenv("CERTACTUM_REQUIRE_MFA", "true")
    monkeypatch.delenv("OBRASIGNAL_REQUIRE_MFA", raising=False)
    assert _mfa_required() is False
    _enforce_mfa_assurance({})

    monkeypatch.setenv("CERTACTUM_REQUIRE_MFA", "false")
    monkeypatch.setenv("OBRASIGNAL_REQUIRE_MFA", "true")
    assert _mfa_required() is True
    with pytest.raises(InvalidTokenError, match="mfa assurance"):
        _enforce_mfa_assurance({"aal": "aal1"})
    _enforce_mfa_assurance({"aal": "aal2"})


def test_obrasignal_mfa_rejects_ambiguous_configuration(monkeypatch):
    import pytest
    from auth_context import _mfa_required
    monkeypatch.setenv("OBRASIGNAL_REQUIRE_MFA", "maybe")
    with pytest.raises(RuntimeError, match="OBRASIGNAL_REQUIRE_MFA"):
        _mfa_required()


def test_staging_neon_tenant_gate_cannot_be_enabled_in_production(monkeypatch):
    import pytest
    monkeypatch.setenv("OBRASIGNAL_ENV", "production")
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "staging")
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setattr(api, "configured_identity", lambda: (_ for _ in ()).throw(
        AssertionError("identity provider must not run for forbidden staging mode")
    ))
    with pytest.raises(RuntimeError, match="cannot run in production"):
        api._identity()


def test_invalid_tenant_auth_mode_rejected_before_identity_lookup(monkeypatch):
    import pytest
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "stagging")
    monkeypatch.setattr(api, "configured_identity", lambda: (_ for _ in ()).throw(
        AssertionError("Identity provider unexpectedly called")
    ))
    with pytest.raises(RuntimeError, match="Invalid OBRASIGNAL_NEON_COMPANY_AUTH"):
        api._identity()


def test_staging_without_provider_rejected_before_identity_lookup(monkeypatch):
    import pytest
    monkeypatch.setenv("OBRASIGNAL_NEON_COMPANY_AUTH", "staging")
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setattr(api, "configured_identity", lambda: (_ for _ in ()).throw(
        AssertionError("Identity provider unexpectedly called")
    ))
    with pytest.raises(RuntimeError, match="requires provider"):
        api._identity()
