from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from auth_context_jwt import authentication_health


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str
    blocking: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "blocking": self.blocking,
        }


def _database_check(database: str | Path) -> ReadinessCheck:
    path = Path(database)
    if not path.exists():
        return ReadinessCheck("database", "fail", "database_missing", True)
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error:
        return ReadinessCheck("database", "fail", "database_unreadable", True)
    if not row or str(row[0]).strip().lower() != "ok":
        return ReadinessCheck("database", "fail", "database_integrity_failed", True)
    return ReadinessCheck("database", "pass", "database_integrity_ok", True)


def _auth_check() -> ReadinessCheck:
    health = authentication_health()
    mode = str(health.get("mode") or "unknown")
    provider_status = str(health.get("provider_status") or "unknown")
    if mode == "provider" and provider_status in {"ready", "uninitialized"} and health.get("config_present") is True:
        return ReadinessCheck("authentication", "pass", f"provider_{provider_status}", True)
    if mode == "development":
        return ReadinessCheck("authentication", "warn", "development_mode", True)
    return ReadinessCheck("authentication", "fail", f"provider_{provider_status}", True)


def _external_proof_check() -> ReadinessCheck:
    configured = all(
        bool((os.getenv(name) or "").strip())
        for name in ("CERTACTUM_WORM_PROVIDER", "CERTACTUM_TIMESTAMP_PROVIDER")
    )
    return ReadinessCheck(
        "external_proof",
        "pass" if configured else "warn",
        "external_providers_declared" if configured else "external_providers_pending",
        False,
    )


def build_operational_readiness(database: str | Path) -> dict[str, object]:
    checks = (_database_check(database), _auth_check(), _external_proof_check())
    blocking_failures = [check.name for check in checks if check.blocking and check.status == "fail"]
    warnings = [check.name for check in checks if check.status == "warn"]
    return {
        "product": "Certactum",
        "status": "not_ready" if blocking_failures else ("ready_with_warnings" if warnings else "ready"),
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "checks": [check.as_dict() for check in checks],
        "truth_boundary": {
            "production_certification_claimed": False,
            "court_acceptance_guaranteed": False,
            "external_worm_timestamp_may_be_pending": True,
        },
    }
