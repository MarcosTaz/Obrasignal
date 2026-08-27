"""Failing-before: missing Auth config must not reach global sync authority."""

import importlib


def test_missing_auth_configuration_cannot_reach_global_sync(monkeypatch):
    # CI-only resynchronization marker: preserve the exact authority invariant.
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)

    import app
    import preload

    importlib.reload(app)
    importlib.reload(preload)

    calls = []

    def _privileged_sync_probe(*args, **kwargs):
        calls.append("sync")
        return None

    app.sync_once = _privileged_sync_probe
    preload._app.sync_once = _privileged_sync_probe

    client = preload.APP.test_client()
    response = client.post("/sync")

    assert calls == [], "missing Auth config synthesized authority that reached global sync"
    assert response.status_code in {401, 403, 404, 503}
