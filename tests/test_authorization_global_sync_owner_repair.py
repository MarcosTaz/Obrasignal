"""Composed Auth/Authz contract for the legacy platform-wide sync boundary.

Global ingestion is an internal worker responsibility. Missing authentication
configuration must fail at authentication, while an explicitly selected local
identity or an authenticated tenant principal still has no platform-wide sync
authority. None of those HTTP paths may invoke ``sync_once``.
"""

import pytest

import api
import app
from auth_context import RequestIdentity


def _probe_sync(monkeypatch):
    calls = []

    def fake_sync_once(*args, **kwargs):
        calls.append("sync")
        return None

    monkeypatch.setattr(app, "sync_once", fake_sync_once)
    response = api.APP.test_client().post("/sync")
    return response, calls


def test_authenticated_principal_alone_cannot_trigger_global_sync(monkeypatch):
    identity = RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject="user-a",
        claims={"sub": "user-a"},
    )
    monkeypatch.setattr(api._preload, "configured_identity", lambda: identity)

    response, calls = _probe_sync(monkeypatch)

    assert calls == []
    assert response.status_code == 403
    assert response.get_json()["code"] == "global_sync_forbidden"


def test_explicit_development_identity_cannot_trigger_global_sync(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "default")

    response, calls = _probe_sync(monkeypatch)

    assert calls == []
    assert response.status_code == 403
    assert response.get_json()["code"] == "global_sync_forbidden"


def test_missing_auth_configuration_fails_before_global_sync(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)

    response, calls = _probe_sync(monkeypatch)

    # In the composed #557 x #556 tree, authentication failure has precedence
    # over authorization failure. The critical invariant is that sync_once is
    # unreachable; 401 is therefore the truthful boundary, not #556's isolated
    # 403 expectation from the former development fallback semantics.
    assert calls == []
    assert response.status_code == 401


def test_internal_background_worker_keeps_sync_authority(monkeypatch):
    calls = []

    def fake_sync_once():
        calls.append("sync")

    def stop_after_one_cycle(_seconds):
        raise RuntimeError("stop-worker-probe")

    monkeypatch.setattr(app, "sync_once", fake_sync_once)
    monkeypatch.setattr(app.time, "sleep", stop_after_one_cycle)

    with pytest.raises(RuntimeError, match="stop-worker-probe"):
        app.worker()

    assert calls == ["sync"]
