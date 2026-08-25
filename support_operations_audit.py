"""Deterministic repository audit for the Support & Incident Operations manifest."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from support_operations import (
    CustomerFailureClass,
    IncidentImpact,
    IncidentSeverity,
    ServiceArea,
    ServiceReadiness,
)


DEFAULT_MANIFEST = Path(__file__).with_name("support_operations_manifest.json")
_REQUIRED_JOURNEYS = {
    "signup_login",
    "profile",
    "radar",
    "sources",
    "opportunity_detail",
    "evidence",
    "workflow",
    "notifications",
    "evaluation",
    "billing",
    "account_privacy",
}
_REQUIRED_RUNBOOKS = {
    "auth_outage",
    "database_degradation",
    "source_outage",
    "stale_radar",
    "billing_verification_failure",
    "notification_failure",
    "bad_deployment",
    "migration_failure",
    "cross_tenant_suspicion",
    "data_corruption",
    "external_dependency_outage",
}
_EXPECTED_SEVERITY = {
    IncidentSeverity.SEV0.value: {
        IncidentImpact.TENANT_LEAKAGE.value,
        IncidentImpact.DATA_LOSS.value,
        IncidentImpact.SECURITY_COMPROMISE.value,
    },
    IncidentSeverity.SEV1.value: {
        IncidentImpact.BILLING_ACCESS_OUTAGE.value,
        IncidentImpact.CUSTOMER_JOURNEY_OUTAGE.value,
    },
    IncidentSeverity.SEV2.value: {IncidentImpact.SOURCE_DEGRADATION.value},
    IncidentSeverity.SEV3.value: {IncidentImpact.SINGLE_CUSTOMER_DEFECT.value},
}
_REQUIRED_FALSE_CLAIM_GUARDS = {
    "WORKAROUND_EQUALS_FIX",
    "GREEN_CI_EQUALS_INCIDENT_RESOLVED",
    "SERVICE_RESTORED_EQUALS_ROOT_CAUSE_CLOSED",
    "UNKNOWN_EQUALS_SUCCESS",
    "CANDIDATE_EQUALS_DEPLOYED",
    "EMPTY_SOURCE_EQUALS_ZERO_MARKET",
}


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("support operations manifest must be a JSON object")
    return data


def audit_manifest(data: dict[str, Any]) -> list[str]:
    """Return deterministic contract violations without mutating repository state."""
    failures: list[str] = []

    expected_failures = {item.value for item in CustomerFailureClass}
    if set(data.get("customer_failure_classes", [])) != expected_failures:
        failures.append("customer failure taxonomy drift")

    expected_readiness = {item.value for item in ServiceReadiness}
    if set(data.get("service_readiness", [])) != expected_readiness:
        failures.append("service readiness taxonomy drift")

    expected_areas = {item.value for item in ServiceArea}
    if set(data.get("service_areas", [])) != expected_areas:
        failures.append("service area taxonomy drift")

    observed_severity = data.get("incident_severity")
    if not isinstance(observed_severity, dict):
        failures.append("incident severity policy missing")
    else:
        normalized = {
            str(severity): set(impacts) if isinstance(impacts, list) else set()
            for severity, impacts in observed_severity.items()
        }
        if normalized != _EXPECTED_SEVERITY:
            failures.append("incident severity policy drift")

    journeys = data.get("journeys")
    if not isinstance(journeys, list):
        failures.append("journey supportability map missing")
    else:
        ids = [row.get("id") for row in journeys if isinstance(row, dict)]
        if len(ids) != len(set(ids)):
            failures.append("duplicate journey id")
        if set(ids) != _REQUIRED_JOURNEYS:
            failures.append("journey supportability coverage drift")
        for row in journeys:
            if not isinstance(row, dict):
                failures.append("malformed journey row")
                continue
            refs = row.get("owner_refs")
            if not isinstance(refs, list) or not refs or any(
                not isinstance(ref, int) or isinstance(ref, bool) or ref <= 0 for ref in refs
            ):
                failures.append(f"journey {row.get('id')!r} lacks bounded owner refs")
            recovery = row.get("recovery")
            if not isinstance(recovery, str) or not recovery:
                failures.append(f"journey {row.get('id')!r} lacks recovery contract")

    runbooks = data.get("runbook_overlays")
    normalized_runbooks = set(runbooks) if isinstance(runbooks, list) else set()
    if normalized_runbooks != _REQUIRED_RUNBOOKS:
        failures.append("runbook overlay coverage drift")

    boundaries = data.get("specialist_boundaries")
    if not isinstance(boundaries, dict) or not boundaries:
        failures.append("specialist ownership boundaries missing")
    else:
        for owner, refs in boundaries.items():
            if not isinstance(owner, str) or not owner:
                failures.append("invalid specialist owner key")
            if not isinstance(refs, list) or not refs or any(
                not isinstance(ref, int) or isinstance(ref, bool) or ref <= 0 for ref in refs
            ):
                failures.append(f"specialist boundary {owner!r} lacks bounded refs")

    if set(data.get("forbidden_claims", [])) != _REQUIRED_FALSE_CLAIM_GUARDS:
        failures.append("false-resolution guard drift")

    owner_issue = data.get("owner_issue")
    if not isinstance(owner_issue, int) or isinstance(owner_issue, bool) or owner_issue <= 0:
        failures.append("owner issue is missing or invalid")

    base = data.get("canonical_base_at_reconstruction")
    if not isinstance(base, str) or len(base) != 40 or any(ch not in "0123456789abcdef" for ch in base):
        failures.append("canonical reconstruction SHA is missing or invalid")

    return failures


def run(path: str | Path = DEFAULT_MANIFEST) -> list[str]:
    return audit_manifest(load_manifest(path))


if __name__ == "__main__":
    problems = run()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        raise SystemExit(1)
    print("SUPPORT_OPERATIONS_AUDIT_OK")
