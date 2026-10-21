from __future__ import annotations

import os

from .security import secret_is_usable


def _present(name: str) -> bool:
    return bool(os.getenv(name))


def readiness_snapshot() -> dict:
    """Return configuration readiness without returning any credential material."""
    admin_present = _present("FCC_ADMIN_TOKEN")
    session_present = _present("FCC_SESSION_SECRET")
    factory_present = _present("FCC_FACTORY_INGEST_TOKEN")
    metric_present = _present("FCC_METRIC_INGEST_TOKEN")
    github_present = _present("FCC_GITHUB_TOKEN")

    admin = secret_is_usable(os.getenv("FCC_ADMIN_TOKEN"), 16)
    session = secret_is_usable(os.getenv("FCC_SESSION_SECRET"), 32)
    factory_feed = secret_is_usable(os.getenv("FCC_FACTORY_INGEST_TOKEN"), 16)
    metric_feed = secret_is_usable(os.getenv("FCC_METRIC_INGEST_TOKEN"), 16)
    github = secret_is_usable(os.getenv("FCC_GITHUB_TOKEN"), 16)
    secure_cookie = os.getenv("FCC_SECURE_COOKIE", "1") == "1"
    persistent_db = bool(os.getenv("FCC_DB"))

    return {
        "private_access": {
            "state": "CONFIGURED" if admin and session else "BLOCKED",
            "admin_token_configured": admin,
            "session_secret_configured": session,
            "admin_token_present": admin_present,
            "session_secret_present": session_present,
        },
        "transport_policy": {
            "state": "CONFIGURED" if secure_cookie else "LOCAL_ONLY",
            "secure_cookie": secure_cookie,
        },
        "health_network_policy": {
            "state": "PARTIAL",
            "claim": "Public-address and redirect validation is enforced, but connection-time DNS is not pinned; DNS rebinding remains a residual risk.",
        },
        "factory_feed": {
            "state": "CONFIGURED" if factory_feed else "NOT_CONFIGURED",
            "token_configured": factory_feed,
            "token_present": factory_present,
        },
        "business_metric_feed": {
            "state": "CONFIGURED" if metric_feed else "NOT_CONFIGURED",
            "token_configured": metric_feed,
            "token_present": metric_present,
        },
        "private_github": {
            "state": "CONFIGURED" if github else "OPTIONAL_NOT_CONFIGURED",
            "token_configured": github,
            "token_present": github_present,
        },
        "persistence": {
            "state": "CONFIGURED" if persistent_db else "DEFAULT_LOCAL_PATH",
            "explicit_db_path_configured": persistent_db,
        },
        "two_factor": {
            "state": "NOT_CONNECTED",
            "claim": "2FA is not provided by this MVP until a real identity provider is integrated.",
        },
        "production_authority": {
            "state": "OWNER_CONTROLLED",
            "claim": "Readiness diagnostics never authorize merge, deployment, billing, outreach or destructive actions.",
        },
    }
