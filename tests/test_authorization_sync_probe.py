"""Authorization-integrity failing-before for the legacy global sync route.

The production compatibility layer already authenticates /sync. This probe starts
after successful authentication and proves the stricter deny-by-default invariant:
an authenticated principal alone must not gain authority to trigger a global source
synchronization side effect when no explicit sync capability/role policy exists.
"""

import api
import app
from auth_context import RequestIdentity


def test_authenticated_principal_alone_cannot_trigger_global_sync(monkeypatch):
    identity = RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject="user-a",
        claims={"sub": "user-a"},
    )
    calls = []

    # Isolate authorization from Auth provider mechanics: authentication has
    # already succeeded for a normal tenant principal.
    monkeypatch.setattr(api._preload, "configured_identity", lambda: identity)

    def fake_sync_once():
        calls.append("sync")

    monkeypatch.setattr(app, "sync_once", fake_sync_once)

    response = api.APP.test_client().post("/sync")

    # Side-effect reachability is the primary authorization invariant. Keep it
    # before the transport assertion so failing-before evidence cannot be
    # misread as a redirect-shape defect.
    assert calls == []
    assert response.status_code in {403, 404}
