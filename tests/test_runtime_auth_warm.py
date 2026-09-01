from threading import Lock

import runtime_auth_warm as warm


class FakeVerifier:
    def __init__(self, fetch):
        self._lock = Lock()
        self._keys = None
        self._expires_at = 0.0
        self._fetched_at = 0.0
        self._retry_at = 0.0
        self._generation = 0
        self._keys_source = None
        self._provider_degraded = False
        self._provider_error = None
        self.cache_seconds = 3600
        self._fetch = fetch

    def _fetch_jwks(self):
        return self._fetch()


def test_provider_keys_are_warmed_before_customer_requests(monkeypatch):
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        return {"kid-a": {"kid": "kid-a"}}

    verifier = FakeVerifier(fetch)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setattr(warm, "production_verifier", lambda: verifier)

    first = warm.warm_production_auth()
    second = warm.warm_production_auth()

    assert first == {"status": "ready", "source": "remote"}
    assert second["status"] == "ready"
    assert calls == 1
    assert verifier._keys == {"kid-a": {"kid": "kid-a"}}
    assert verifier._provider_degraded is False


def test_provider_warm_failure_does_not_make_startup_claim_ready(monkeypatch):
    verifier = FakeVerifier(lambda: (_ for _ in ()).throw(TimeoutError("provider slow")))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setattr(warm, "production_verifier", lambda: verifier)

    state = warm.warm_production_auth()

    assert state == {"status": "degraded"}
    assert verifier._keys is None
    assert verifier._provider_degraded is True
    assert verifier._provider_error == "timeout"
    assert verifier._retry_at > 0


def test_development_does_not_touch_provider(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setattr(
        warm,
        "production_verifier",
        lambda: (_ for _ in ()).throw(AssertionError("must not load provider")),
    )

    assert warm.warm_production_auth() == {"status": "not_applicable"}
