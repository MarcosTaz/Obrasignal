from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

import auth_context_jwt
import cors_app


ROOT = Path(__file__).resolve().parents[1]


def test_parallel_cold_key_lookups_share_one_jwks_fetch():
    verifier = auth_context_jwt.JwtVerifier(
        "https://issuer.example/auth/v1",
        cache_seconds=3600,
        stale_max_seconds=86400,
    )
    calls = 0
    calls_lock = threading.Lock()

    def fetch():
        nonlocal calls
        with calls_lock:
            calls += 1
        # Keep the first caller inside the single-flight section long enough for
        # the other workers to contend on the same cold cache deterministically.
        time.sleep(0.05)
        return {"shared-kid": {"kid": "shared-kid"}}

    verifier._fetch_jwks = fetch
    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = list(pool.map(lambda _: verifier._key_for("shared-kid"), range(16)))

    assert calls == 1
    assert len(keys) == 16
    assert all(key["kid"] == "shared-kid" for key in keys)


def test_global_preflight_handler_itself_never_touches_auth_or_db(monkeypatch):
    def bomb(*_args, **_kwargs):
        raise AssertionError("OPTIONS preflight must not touch auth or SQLite")

    monkeypatch.setattr(cors_app, "configured_identity", bomb)
    import app
    monkeypatch.setattr(app, "db", bomb)

    with cors_app.APP.test_request_context(
        "/api/v1/opportunities",
        method="OPTIONS",
        headers={
            "Origin": "https://obrasignal.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    ):
        response = cors_app._global_api_preflight()

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "https://obrasignal.com"


def test_production_entrypoint_puts_preflight_ahead_of_all_transitive_guards():
    source = (ROOT / "production_entrypoint.py").read_text(encoding="utf-8")
    remove_at = source.index("_global_hooks.remove(_global_api_preflight)")
    first_at = source.index("_global_hooks.insert(0, _global_api_preflight)")
    warm_at = source.index("AUTH_WARM_STATE = warm_production_auth()")
    assert remove_at < first_at < warm_at
