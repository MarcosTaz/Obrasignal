from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from auth_context_jwt import authentication_health
from vertical_apps.industrial_claims.production_trust_runtime import configured_production_trust_gate


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str
    blocking: bool

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "status": self.status, "detail": self.detail, "blocking": self.blocking}


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


def _external_proof_checks() -> tuple[ReadinessCheck, ReadinessCheck]:
    """Resolve system-level WORM/timestamp readiness from live probes only.

    Operational readiness checks the external controls independently from a
    particular user request. Per-request AAL2 remains enforced by
    ProductionTrustGate.require_ready inside the secure intake route.
    """
    gate = configured_production_trust_gate()
    if gate is None:
        return (
            ReadinessCheck("worm_storage", "fail", "live_worm_probe_unconfigured", True),
            ReadinessCheck("trusted_timestamp", "fail", "live_timestamp_probe_unconfigured", True),
        )

    try:
        # AAL2 is supplied only to isolate the external-control probes for this
        # system readiness report. Real intake never uses this synthetic claim;
        # the request route verifies the actual signed JWT claims separately.
        decision = gate.evaluate(verified_claims={"aal": "aal2"})
    except Exception:
        return (
            ReadinessCheck("worm_storage", "fail", "live_worm_probe_error", True),
            ReadinessCheck("trusted_timestamp", "fail", "live_timestamp_probe_error", True),
        )

    blockers = set(decision.blockers)
    worm_ready = "worm_unverified" not in blockers and "control_identity_invalid" not in blockers
    timestamp_ready = "timestamp_unverified" not in blockers and "control_identity_invalid" not in blockers
    return (
        ReadinessCheck(
            "worm_storage",
            "pass" if worm_ready else "fail",
            "live_worm_probe_verified" if worm_ready else "live_worm_probe_unverified",
            True,
        ),
        ReadinessCheck(
            "trusted_timestamp",
            "pass" if timestamp_ready else "fail",
            "live_timestamp_probe_verified" if timestamp_ready else "live_timestamp_probe_unverified",
            True,
        ),
    )


def build_operational_readiness(database: str | Path) -> dict[str, object]:
    checks = (_database_check(database), _auth_check(), *_external_proof_checks())
    blocking_failures = [check.name for check in checks if check.blocking and check.status == "fail"]
    warnings = [check.name for check in checks if check.status == "warn"]
    external_proof_ready = all(
        check.status == "pass" for check in checks if check.name in {"worm_storage", "trusted_timestamp"}
    )
    auth_ready = next(check.status == "pass" for check in checks if check.name == "authentication")
    database_ready = next(check.status == "pass" for check in checks if check.name == "database")
    real_evidence_intake_enabled = database_ready and auth_ready and external_proof_ready and not blocking_failures
    return {
        "product": "VINDORUM",
        "status": "ready" if real_evidence_intake_enabled and not warnings else (
            "ready_with_warnings" if real_evidence_intake_enabled else "not_ready"
        ),
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "checks": [check.as_dict() for check in checks],
        "activation": {
            "automatic": True,
            "real_evidence_intake_enabled": real_evidence_intake_enabled,
            "rule": "database_ok AND production_auth_ok AND live_worm_probe_ok AND live_timestamp_probe_ok",
        },
        "truth_boundary": {
            "production_certification_claimed": False,
            "court_acceptance_guaranteed": False,
            "provider_declaration_is_not_external_certification": True,
            "provider_declaration_cannot_enable_intake": True,
            "external_controls_require_live_probe_receipts": True,
            "per_request_mfa_aal2_still_required": True,
        },
    }
