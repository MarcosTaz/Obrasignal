"""Data-quality/privacy contracts for ObraSignal measurement.

This layer deliberately records UNKNOWN policy boundaries rather than inventing a
retention period or deletion/export guarantee. It also provides reusable guards for
future event bridges without changing any current domain owner or event store.
"""
from __future__ import annotations

from copy import deepcopy

from analytics_measurement import SCHEMA_VERSION, event_taxonomy

QUALITY_VERSION = "analytics-quality-v1"

UNKNOWN_POLICY = {
    "status": "UNKNOWN",
    "reason": "no canonical analytics-specific policy is proven on current main",
    "owner_boundary": "Account/Privacy + Data Reliability",
}

# Analytics should need technical identity/status only. These keys are intentionally
# narrow enough for future route-owner bridges such as #339 and Notification.
DEFAULT_ALLOWED_METADATA_KEYS = frozenset({
    "source",
    "external_id",
    "workflow_status",
    "delivery_status",
    "reason_code",
    "event_id",
    "schema_version",
})

_PROHIBITED_KEY_TOKENS = frozenset({
    "token",
    "secret",
    "password",
    "authorization",
    "email",
    "phone",
    "address",
    "title",
    "buyer",
    "note",
    "profile",
    "raw",
    "payload",
    "request",
    "body",
    "content",
})


def metric_contracts():
    """Return measurement contracts enriched with mandatory quality boundaries."""
    contracts = event_taxonomy()
    for contract in contracts.values():
        contract["measurement_schema_version"] = SCHEMA_VERSION
        contract["quality_schema_version"] = QUALITY_VERSION
        contract["retention"] = deepcopy(UNKNOWN_POLICY)
        contract["deletion_export"] = {
            "status": "UNKNOWN",
            "reason": "analytics deletion/export behavior is not separately proven; consume Account/Privacy contract before persistent analytics storage",
            "owner_boundary": "Account/Privacy + Data Reliability",
        }
        contract["privacy"] = {
            "mode": "MINIMIZED_TECHNICAL_METADATA_ONLY",
            "allowed_metadata_keys": sorted(DEFAULT_ALLOWED_METADATA_KEYS),
            "raw_customer_or_procurement_payload": "FORBIDDEN",
        }
    return contracts


def validate_metric_contracts():
    required = {
        "measurement_schema_version",
        "quality_schema_version",
        "retention",
        "deletion_export",
        "privacy",
    }
    failures = {}
    for name, contract in metric_contracts().items():
        missing = sorted(required - set(contract))
        if missing:
            failures[name] = missing
        for policy_name in ("retention", "deletion_export"):
            if contract[policy_name].get("status") not in {"PROVEN", "UNKNOWN"}:
                failures.setdefault(name, []).append(f"invalid_{policy_name}_status")
    if failures:
        raise ValueError({"invalid_metric_quality_contract": failures})
    return True


def validate_event_metadata(metadata, *, allowed_keys=None):
    """Validate privacy-minimal event metadata without inspecting customer content.

    Values are deliberately not interpreted. The contract rejects disallowed keys so
    a caller cannot accidentally send raw profile/procurement/customer payloads into
    an analytics path under a harmless-looking event name.
    """
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("analytics_metadata_must_be_object")
    allowed = set(DEFAULT_ALLOWED_METADATA_KEYS if allowed_keys is None else allowed_keys)
    clean = {}
    for key, value in metadata.items():
        normalized = str(key).strip().lower()
        if not normalized:
            raise ValueError("analytics_metadata_empty_key")
        if any(token in normalized for token in _PROHIBITED_KEY_TOKENS):
            raise ValueError(f"analytics_metadata_prohibited_key:{normalized}")
        if normalized not in allowed:
            raise ValueError(f"analytics_metadata_unapproved_key:{normalized}")
        if isinstance(value, (dict, list, tuple, set)):
            raise ValueError(f"analytics_metadata_nested_value_forbidden:{normalized}")
        clean[normalized] = value
    return clean


def rate_contract(*, numerator, denominator, eligibility, missing_behavior):
    """Construct a rate definition only when its decision semantics are explicit."""
    fields = {
        "numerator": numerator,
        "denominator": denominator,
        "eligibility": eligibility,
        "missing_behavior": missing_behavior,
    }
    missing = [name for name, value in fields.items() if not str(value or "").strip()]
    if missing:
        raise ValueError({"incomplete_rate_contract": missing})
    return {
        **fields,
        "schema_version": QUALITY_VERSION,
        "zero_denominator_behavior": "RATE_UNKNOWN",
        "unknown_data_behavior": "EXCLUDE_ONLY_IF_EXPLICITLY_JUSTIFIED; OTHERWISE RATE_UNKNOWN",
    }
