"""Owner repair for the legacy platform-wide sync mutation boundary.

Global ingestion is an internal worker responsibility. Until ObraSignal defines an
explicit server/operator capability, neither a normal authenticated tenant nor the
development fallback identity may authorize POST /sync.
"""

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


def test_missing_auth_configuration_cannot_trigger_global_sync(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)

    response, calls = _probe_sync(monkeypatch)

    assert calls == []
    assert response.status_code == 403
    assert response.get_json()["code"] == "global_sync_forbidden"
