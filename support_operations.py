"""Support-facing incident semantics for ObraSignal.

This module is deliberately transport/runtime neutral. It does not own service
health, authentication, billing, storage recovery, source health, or production
mutation. It provides a bounded vocabulary that support tooling can consume
without creating a second operational source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any, Iterable, Mapping


class CustomerFailureClass(str, Enum):
    RETRYABLE = "RETRYABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INVALID_INPUT = "INVALID_INPUT"


class IncidentSeverity(str, Enum):
    SEV0 = "SEV0"
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"


class IncidentImpact(str, Enum):
    TENANT_LEAKAGE = "TENANT_LEAKAGE"
    DATA_LOSS = "DATA_LOSS"
    SECURITY_COMPROMISE = "SECURITY_COMPROMISE"
    BILLING_ACCESS_OUTAGE = "BILLING_ACCESS_OUTAGE"
    CUSTOMER_JOURNEY_OUTAGE = "CUSTOMER_JOURNEY_OUTAGE"
    SOURCE_DEGRADATION = "SOURCE_DEGRADATION"
    SINGLE_CUSTOMER_DEFECT = "SINGLE_CUSTOMER_DEFECT"


class ServiceReadiness(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ServiceArea(str, Enum):
    AUTH = "AUTH"
    DATA = "DATA"
    SOURCES = "SOURCES"
    WEB = "WEB"
    MOBILE = "MOBILE"
    NOTIFICATIONS = "NOTIFICATIONS"
    BILLING = "BILLING"
    PRIVACY = "PRIVACY"
    RECOVERY = "RECOVERY"
    OBSERVABILITY = "OBSERVABILITY"
    SUPPORT = "SUPPORT"


class RecoveryState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SERVICE_RESTORED = "SERVICE_RESTORED"
    VERIFIED = "VERIFIED"
    ROOT_CAUSE_CLOSED = "ROOT_CAUSE_CLOSED"


_SEVERITY_BY_IMPACT = {
    IncidentImpact.TENANT_LEAKAGE: IncidentSeverity.SEV0,
    IncidentImpact.DATA_LOSS: IncidentSeverity.SEV0,
    IncidentImpact.SECURITY_COMPROMISE: IncidentSeverity.SEV0,
    IncidentImpact.BILLING_ACCESS_OUTAGE: IncidentSeverity.SEV1,
    IncidentImpact.CUSTOMER_JOURNEY_OUTAGE: IncidentSeverity.SEV1,
    IncidentImpact.SOURCE_DEGRADATION: IncidentSeverity.SEV2,
    IncidentImpact.SINGLE_CUSTOMER_DEFECT: IncidentSeverity.SEV3,
}
_SEVERITY_ORDER = {
    IncidentSeverity.SEV0: 0,
    IncidentSeverity.SEV1: 1,
    IncidentSeverity.SEV2: 2,
    IncidentSeverity.SEV3: 3,
}

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._:/+-]{1,256}$")
_STRING_DETAIL_KEYS = frozenset({"operation", "error_code", "component", "dependency_status"})
_INTEGER_DETAIL_RANGES = {
    "http_status": (100, 599),
    "retry_after_seconds": (0, 86_400),
    "attempt": (0, 1_000),
    "state_version": (0, (2**63) - 1),
}
_DETAIL_KEYS = _STRING_DETAIL_KEYS | frozenset(_INTEGER_DETAIL_RANGES)
_MAX_DETAIL_ITEMS = 8
_MAX_TEXT = 256


def classify_incident(impacts: Iterable[IncidentImpact | str]) -> IncidentSeverity:
    """Return the highest supported severity from explicit observed impacts.

    An empty impact set is not silently turned into a low-severity incident.
    """
    normalized: set[IncidentImpact] = set()
    for impact in impacts:
        try:
            normalized.add(impact if isinstance(impact, IncidentImpact) else IncidentImpact(impact))
        except ValueError as exc:
            raise ValueError(f"unsupported incident impact: {impact!r}") from exc
    if not normalized:
        raise ValueError("incident impact evidence is required")
    return min((_SEVERITY_BY_IMPACT[impact] for impact in normalized), key=_SEVERITY_ORDER.__getitem__)


def service_readiness_matrix(
    evidence: Mapping[ServiceArea | str, ServiceReadiness | str] | None = None,
) -> dict[str, str]:
    """Return the complete service matrix, defaulting missing owner evidence to UNKNOWN.

    This function never promotes a service to HEALTHY merely because no failure
    is present in Support. Callers must supply an explicit canonical readiness
    value from the relevant owning contract.
    """
    matrix = {area.value: ServiceReadiness.UNKNOWN.value for area in ServiceArea}
    if evidence is None:
        return matrix
    if not isinstance(evidence, Mapping):
        raise ValueError("service readiness evidence must be a mapping")
    for raw_area, raw_state in evidence.items():
        try:
            area = raw_area if isinstance(raw_area, ServiceArea) else ServiceArea(raw_area)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported service area: {raw_area!r}") from exc
        try:
            state = raw_state if isinstance(raw_state, ServiceReadiness) else ServiceReadiness(raw_state)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported service readiness: {raw_state!r}") from exc
        matrix[area.value] = state.value
    return matrix


def recovery_state(
    *,
    started: bool,
    service_restored: bool,
    recovery_verified: bool,
    root_cause_closed: bool,
) -> RecoveryState:
    """Represent recovery without collapsing restoration into verified closure."""
    flags = {
        "started": started,
        "service_restored": service_restored,
        "recovery_verified": recovery_verified,
        "root_cause_closed": root_cause_closed,
    }
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError("recovery state inputs must be booleans")
    if root_cause_closed and not recovery_verified:
        raise ValueError("root cause cannot be closed before recovery is verified")
    if recovery_verified and not service_restored:
        raise ValueError("recovery cannot be verified before service is restored")
    if service_restored and not started:
        raise ValueError("service cannot be restored before recovery starts")
    if root_cause_closed:
        return RecoveryState.ROOT_CAUSE_CLOSED
    if recovery_verified:
        return RecoveryState.VERIFIED
    if service_restored:
        return RecoveryState.SERVICE_RESTORED
    if started:
        return RecoveryState.IN_PROGRESS
    return RecoveryState.NOT_STARTED


def _bounded_text(name: str, value: str | None, *, token: bool = False) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > _MAX_TEXT:
        raise ValueError(f"{name} must be a non-empty bounded string")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name} contains control characters")
    if token and not _SAFE_TOKEN.fullmatch(value):
        raise ValueError(f"{name} contains unsupported characters")
    return value


def _observed_at(value: str) -> str:
    value = _bounded_text("observed_at", value)  # type: ignore[assignment]
    assert value is not None
    iso_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return value


def _safe_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    if details is None:
        return {}
    if not isinstance(details, Mapping):
        raise ValueError("support evidence details must be a mapping")
    if len(details) > _MAX_DETAIL_ITEMS:
        raise ValueError("too many support evidence details")
    unknown = set(details) - _DETAIL_KEYS
    if unknown:
        raise ValueError(f"unsupported support evidence fields: {sorted(unknown)}")
    clean: dict[str, Any] = {}
    for key, value in details.items():
        if key in _STRING_DETAIL_KEYS:
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a bounded token-like string")
            clean[key] = _bounded_text(key, value, token=True)
            continue
        lower, upper = _INTEGER_DETAIL_RANGES[key]
        if not isinstance(value, int) or isinstance(value, bool) or not (lower <= value <= upper):
            raise ValueError(f"{key} must be an integer in range {lower}..{upper}")
        clean[key] = value
    return clean


@dataclass(frozen=True)
class SupportEvidencePack:
    correlation_id: str
    observed_at: str
    service_area: ServiceArea
    failure_class: CustomerFailureClass
    service_readiness: ServiceReadiness
    recovery_state: RecoveryState
    build: str | None = None
    version: str | None = None
    dependency_state: str | None = None
    details: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return only bounded operational metadata; no tenant selector/payload."""
        if not isinstance(self.correlation_id, str) or not _CORRELATION_ID.fullmatch(self.correlation_id):
            raise ValueError("correlation_id must be an opaque bounded identifier")
        enum_fields = {
            "service_area": (self.service_area, ServiceArea),
            "failure_class": (self.failure_class, CustomerFailureClass),
            "service_readiness": (self.service_readiness, ServiceReadiness),
            "recovery_state": (self.recovery_state, RecoveryState),
        }
        for name, (value, enum_type) in enum_fields.items():
            if not isinstance(value, enum_type):
                raise ValueError(f"{name} must use the canonical support enum")
        observed_at = _observed_at(self.observed_at)
        build = _bounded_text("build", self.build, token=True)
        version = _bounded_text("version", self.version, token=True)
        dependency_state = _bounded_text("dependency_state", self.dependency_state, token=True)
        details = _safe_details(self.details)
        return {
            "correlation_id": self.correlation_id,
            "observed_at": observed_at,
            "service_area": self.service_area.value,
            "failure_class": self.failure_class.value,
            "service_readiness": self.service_readiness.value,
            "recovery_state": self.recovery_state.value,
            "build": build,
            "version": version,
            "dependency_state": dependency_state,
            "details": details,
        }


def customer_error_payload(
    failure_class: CustomerFailureClass | str,
    *,
    correlation_id: str,
) -> dict[str, str]:
    """Build a deliberately small customer-safe error envelope.

    Retryability, root cause, success, tenant identity, and recovery are not
    guessed here. Those require evidence from their owning contracts.
    """
    try:
        failure = (
            failure_class
            if isinstance(failure_class, CustomerFailureClass)
            else CustomerFailureClass(failure_class)
        )
    except ValueError as exc:
        raise ValueError(f"unsupported customer failure class: {failure_class!r}") from exc
    if not isinstance(correlation_id, str) or not _CORRELATION_ID.fullmatch(correlation_id):
        raise ValueError("correlation_id must be an opaque bounded identifier")
    return {"error_class": failure.value, "correlation_id": correlation_id}
