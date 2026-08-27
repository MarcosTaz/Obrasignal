from __future__ import annotations

import os


def _configured(name: str) -> bool:
    return bool(os.getenv(name))


def readiness_snapshot() -> dict:
    """Return configuration readiness without returning any credential material."""
    admin = _configured("FCC_ADMIN_TOKEN")
    session = _configured("FCC_SESSION_SECRET")
    secure_cookie = os.getenv("FCC_SECURE_COOKIE", "1") == "1"
    factory_feed = _configured("FCC_FACTORY_INGEST_TOKEN")
    metric_feed = _configured("FCC_METRIC_INGEST_TOKEN")
    github = _configured("FCC_GITHUB_TOKEN")
    persistent_db = bool(os.getenv("FCC_DB"))

    return {
        "private_access": {
            "state": "CONFIGURED" if admin and session else "BLOCKED",
            "admin_token_configured": admin,
            "session_secret_configured": session,
        },
        "transport_policy": {
            "state": "CONFIGURED" if secure_cookie else "LOCAL_ONLY",
            "secure_cookie": secure_cookie,
        },
        "factory_feed": {
            "state": "CONFIGURED" if factory_feed else "NOT_CONFIGURED",
            "token_configured": factory_feed,
        },
        "business_metric_feed": {
            "state": "CONFIGURED" if metric_feed else "NOT_CONFIGURED",
            "token_configured": metric_feed,
        },
        "private_github": {
            "state": "CONFIGURED" if github else "OPTIONAL_NOT_CONFIGURED",
            "token_configured": github,
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
