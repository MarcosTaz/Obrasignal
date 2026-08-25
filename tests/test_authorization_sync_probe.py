"""Authorization-integrity failing-before for the legacy global sync route.

This probe intentionally chooses no positive admin/operator policy. It proves only
the deny-by-default invariant: an unauthenticated provider-mode request must not
be able to trigger the global source synchronization side effect.
"""

import app


def test_unauthenticated_provider_request_cannot_trigger_global_sync(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    calls = []

    def fake_sync_once():
        calls.append("sync")

    monkeypatch.setattr(app, "sync_once", fake_sync_once)

    response = app.APP.test_client().post("/sync")

    assert response.status_code in {401, 403, 404}
    assert calls == []
