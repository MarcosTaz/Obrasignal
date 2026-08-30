"""Privacy-safe failure observability registry for ObraSignal.

A failure surface is not considered healthy merely because Analytics cannot count it.
The registry separates durable observation, log-only signals, and missing measurement.
"""
from __future__ import annotations

from copy import deepcopy

FAILURE_VERSION = "failure-measurement-v1"

_FAILURES = {
    "auth_failure": {
        "measurement_status": "PARTIAL",
        "source_owner": "Production Auth",
        "evidence": "bounded structured logs: auth_failure reason=<category>",
        "durable_count": False,
        "tenant_scope": "request identity may be unresolved on failure; never guess account_id",
        "missing_behavior": "UNKNOWN failure volume; no durable series on current main",
        "privacy": "reason category only; token material forbidden",
    },
    "auth_provider_degradation": {
        "measurement_status": "PARTIAL",
        "source_owner": "Production Auth",
        "evidence": "bounded logs for jwks_unavailable/provider_config",
        "durable_count": False,
        "tenant_scope": "provider/system level",
        "missing_behavior": "UNKNOWN historical volume without log aggregation contract",
        "privacy": "provider status/reason only; secrets and JWT material forbidden",
    },
    "source_degradation": {
        "measurement_status": "OBSERVABLE",
        "source_owner": "Source Health",
        "evidence": "source_health status + last_attempt/last_success/last_error presence",
        "durable_count": False,
        "tenant_scope": "source/system level; not a customer tenant failure count",
        "missing_behavior": "missing source row = UNKNOWN, not healthy",
        "privacy": "Analytics exposes error presence/category only, never raw error text",
    },
    "empty_unknown_radar": {
        "measurement_status": "MISSING",
        "source_owner": "Radar/Source truth owners",
        "evidence": None,
        "durable_count": False,
        "tenant_scope": "required: authenticated account_id",
        "missing_behavior": "UNKNOWN; empty Radar must be separated from source failure/partial coverage/no matches",
        "privacy": "no raw opportunity/profile payload required",
    },
    "billing_verification_failure": {
        "measurement_status": "MISSING",
        "source_owner": "Billing",
        "evidence": "current sync path can return without durable failure classification",
        "durable_count": False,
        "tenant_scope": "required: account_id for customer-impact evidence",
        "missing_behavior": "UNKNOWN/UNAVAILABLE; never synthesize Evaluation or paid state",
        "privacy": "no receipt/token/secret/raw provider payload in Analytics",
    },
    "notification_failure": {
        "measurement_status": "MISSING",
        "source_owner": "Notification #57/#263",
        "evidence": "alert candidate creation exists; terminal delivery failure series not yet canonical",
        "durable_count": False,
        "tenant_scope": "required: account_id + opaque logical event id",
        "missing_behavior": "UNKNOWN; attempted send is not delivered or failed unless provider contract proves it",
        "privacy": "no device token or notification payload in Analytics",
    },
    "workflow_failure": {
        "measurement_status": "MISSING",
        "source_owner": "Workflow/API",
        "evidence": None,
        "durable_count": False,
        "tenant_scope": "required: authenticated account_id",
        "missing_behavior": "UNKNOWN; current workflow state does not retain failed writes",
        "privacy": "no customer note content in Analytics",
    },
    "dependency_degradation": {
        "measurement_status": "PARTIAL",
        "source_owner": "per dependency owner",
        "evidence": "some bounded subsystem health/log signals exist; no canonical cross-dependency series",
        "durable_count": False,
        "tenant_scope": "system level unless explicit customer-impact mapping is proven",
        "missing_behavior": "UNKNOWN for dependencies without a public health contract",
        "privacy": "status/reason category only",
    },
}


def failure_registry():
    return deepcopy(_FAILURES)


def validate_failure_registry():
    required = {
        "measurement_status",
        "source_owner",
        "evidence",
        "durable_count",
        "tenant_scope",
        "missing_behavior",
        "privacy",
    }
    failures = {}
    for name, contract in _FAILURES.items():
        missing = sorted(required - set(contract))
        if missing:
            failures[name] = missing
        if contract["measurement_status"] not in {"OBSERVABLE", "PARTIAL", "MISSING"}:
            failures.setdefault(name, []).append("invalid_measurement_status")
    if failures:
        raise ValueError({"invalid_failure_contract": failures})
    return True


def source_failure_snapshot(conn):
    """Return source failure state without exposing raw error text."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_health'"
    ).fetchone()
    if not exists:
        return {"quality": "UNKNOWN", "sources": [], "reason": "source_health_table_missing"}
    rows = conn.execute(
        "SELECT source,status,last_attempt,last_success,last_error FROM source_health ORDER BY source"
    ).fetchall()
    sources = []
    for row in rows:
        source, status, last_attempt, last_success, last_error = row
        normalized = str(status or "unknown").lower()
        if normalized not in {"healthy", "degraded", "stale", "unknown", "unavailable"}:
            normalized = "unknown"
        sources.append({
            "source": source,
            "status": normalized,
            "last_attempt": last_attempt,
            "last_success": last_success,
            "error_present": bool(last_error),
        })
    return {
        "quality": "OBSERVABLE" if rows else "UNKNOWN",
        "sources": sources,
        "reason": None if rows else "no_source_health_rows; absence is not healthy",
        "schema_version": FAILURE_VERSION,
    }
