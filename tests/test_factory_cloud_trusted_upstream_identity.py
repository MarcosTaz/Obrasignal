import pytest
from flask import Flask, request

from factory_cloud.shared_contracts import SharedContractError
from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier, signed_test_headers

SECRET = "s" * 32
NOW = 1_800_000_000


def _request(
    verifier, *, method="POST", path="/analyze", tenant="tenant-a", actor="actor-a",
    timestamp=NOW, support_role="", mutate=None,
):
    app = Flask(__name__)
    headers = signed_test_headers(
        secret=SECRET, tenant_id=tenant, actor_id=actor,
        method=method, path=path, timestamp=timestamp, support_role=support_role,
    )
    if mutate:
        headers.update(mutate)
    with app.test_request_context(path, method=method, headers=headers):
        return verifier.verify_request(request)


def test_signed_identity_is_bound_to_method_path_tenant_actor_and_time():
    verifier = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)
    identity = _request(verifier)
    assert identity.tenant_id == "tenant-a"
    assert identity.actor_id == "actor-a"

    for method, path, mutate in (
        ("GET", "/analyze", None),
        ("POST", "/other", None),
        ("POST", "/analyze", {"X-Tenant-ID": "tenant-b"}),
        ("POST", "/analyze", {"X-Actor-ID": "actor-b"}),
    ):
        with pytest.raises(SharedContractError, match="signature"):
            _request(verifier, method=method, path=path, mutate=mutate)


def test_support_role_is_cryptographically_bound_and_cannot_be_escalated():
    verifier = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)
    identity = _request(verifier, path="/support/incidents", support_role="support_viewer")
    assert identity.tenant_id == "tenant-a"
    with pytest.raises(SharedContractError, match="signature"):
        _request(
            verifier, path="/support/incidents", support_role="support_viewer",
            mutate={"X-Support-Role": "on_call_admin"},
        )


def test_expired_or_future_signature_fails_closed():
    verifier = TrustedUpstreamVerifier(SECRET, max_age_seconds=120, clock=lambda: NOW)
    for timestamp in (NOW - 121, NOW + 121):
        with pytest.raises(SharedContractError, match="expired"):
            _request(verifier, timestamp=timestamp)


def test_missing_or_short_key_fails_closed(monkeypatch):
    monkeypatch.delenv("ASSISTED_UPSTREAM_HMAC_KEY", raising=False)
    with pytest.raises(SharedContractError, match="not configured"):
        TrustedUpstreamVerifier.from_env()
    with pytest.raises(SharedContractError, match="at least 32 bytes"):
        TrustedUpstreamVerifier("short")


def test_identity_rejects_control_characters_even_with_otherwise_signed_headers():
    verifier = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)
    headers = signed_test_headers(
        secret=SECRET, tenant_id="tenant-a", actor_id="actor-a",
        method="POST", path="/analyze", timestamp=NOW,
    )
    app = Flask(__name__)
    headers["X-Tenant-ID"] = "tenant-a\x00suffix"
    with app.test_request_context("/analyze", method="POST", headers=headers):
        with pytest.raises(SharedContractError, match="invalid trusted upstream tenant"):
            verifier.verify_request(request)
