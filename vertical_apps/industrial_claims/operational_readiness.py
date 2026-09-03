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


def _declared(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _external_proof_checks() -> tuple[ReadinessCheck, ReadinessCheck]:
    worm = _declared("CERTACTUM_WORM_PROVIDER")
    timestamp = _declared("CERTACTUM_TIMESTAMP_PROVIDER")
    return (
        ReadinessCheck("worm_storage", "pass" if worm else "fail", "worm_provider_declared" if worm else "worm_provider_pending", True),
        ReadinessCheck("trusted_timestamp", "pass" if timestamp else "fail", "timestamp_provider_declared" if timestamp else "timestamp_provider_pending", True),
    )


def build_operational_readiness(database: str | Path) -> dict[str, object]:
    checks = (_database_check(database), _auth_check(), *_external_proof_checks())
    blocking_failures = [check.name for check in checks if check.blocking and check.status == "fail"]
    warnings = [check.name for check in checks if check.status == "warn"]
    external_proof_ready = all(check.status == "pass" for check in checks if check.name in {"worm_storage", "trusted_timestamp"})
    auth_ready = next(check.status == "pass" for check in checks if check.name == "authentication")
    database_ready = next(check.status == "pass" for check in checks if check.name == "database")
    real_evidence_intake_enabled = database_ready and auth_ready and external_proof_ready and not blocking_failures
    return {
        "product": "Certactum",
        "status": "ready" if real_evidence_intake_enabled and not warnings else ("ready_with_warnings" if real_evidence_intake_enabled else "not_ready"),
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "checks": [check.as_dict() for check in checks],
        "activation": {
            "automatic": True,
            "real_evidence_intake_enabled": real_evidence_intake_enabled,
            "rule": "database_ok AND production_auth_ok AND worm_provider_declared AND timestamp_provider_declared",
        },
        "truth_boundary": {
            "production_certification_claimed": False,
            "court_acceptance_guaranteed": False,
            "provider_declaration_is_not_external_certification": True,
        },
    }
