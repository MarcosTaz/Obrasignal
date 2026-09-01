"""Prewarm the public JWT verification keyset before a Gunicorn worker is ready.

The first authenticated Web render fan-outs several private API reads. Without a
warm keyset all of those gthreads can wait behind the verifier's single-flight
JWKS lock while one network request is in progress. Warming during worker import
moves that provider I/O outside customer request capacity.

Failure remains fail-closed for authentication: startup is not aborted, but the
verifier is marked degraded and later authenticated requests keep returning the
existing 503 boundary until the normal verifier refresh can recover.
"""
from __future__ import annotations

import os
import time

from auth_context_jwt import _provider_failure_category, production_verifier


def warm_production_auth() -> dict:
    mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if mode != "provider":
        return {"status": "not_applicable"}

    try:
        verifier = production_verifier()
    except (RuntimeError, TypeError, ValueError):
        return {"status": "misconfigured"}

    # JwtVerifier deliberately owns this lock. Startup has no customer request
    # attached to it, so paying the provider network latency here cannot consume
    # a Gunicorn request slot.
    with verifier._lock:
        now = time.time()
        if verifier._keys and now < verifier._expires_at:
            return {"status": "ready", "source": verifier._keys_source or "cache"}
        if now < verifier._retry_at:
            return {"status": "degraded"}
        try:
            refreshed = verifier._fetch_jwks()
        except Exception as exc:
            verifier._provider_degraded = True
            verifier._provider_error = _provider_failure_category(exc)
            verifier._retry_at = time.time() + min(30, verifier.cache_seconds)
            return {"status": "degraded"}

        verifier._keys = refreshed
        verifier._fetched_at = time.time()
        verifier._expires_at = verifier._fetched_at + verifier.cache_seconds
        verifier._retry_at = 0.0
        verifier._generation += 1
        verifier._keys_source = "remote"
        verifier._provider_degraded = False
        verifier._provider_error = None
        return {"status": "ready", "source": "remote"}
