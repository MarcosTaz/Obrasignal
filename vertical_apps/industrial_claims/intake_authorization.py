from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from vertical_apps.industrial_claims.proof import canonical_json_bytes
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore
from vertical_apps.industrial_claims.secure_capture import (
    CaptureIdentity,
    SecureCaptureResult,
    SourceAuthenticationReceipt,
    capture_original_evidence,
)


class IntakeAuthorizationError(ValueError):
    pass


BOUNDED_RAPID_SCAN_PURPOSE = "BOUNDED_HISTORICAL_RAPID_SCAN"
ALLOWED_DATA_TERMS_STATES = {"NOT_REQUIRED", "SIGNED"}
ROLE_SOURCE_TYPES = {
    "commercial_basis": "commercial_basis",
    "event": "industrial_commercial_event",
    "cost": "cost_evidence",
}


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise IntakeAuthorizationError(f"invalid intake authorization {label}")
    return text


def _aware(value: object, *, label: str) -> datetime:
    text = _required(value, label=label, maximum=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntakeAuthorizationError(f"invalid intake authorization {label}") from exc
    if parsed.tzinfo is None:
        raise IntakeAuthorizationError(f"intake authorization {label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IntakeAuthorization:
    authorization_id: str
    tenant_id: str
    case_ref: str
    authorized_by_ref: str
    authorized_at: str
    expires_at: str
    minimum_immutable_retention_until: str
    transfer_channel_ref: str
    evidence_roles: tuple[str, ...]
    data_terms_state: str
    immutable_retention_acknowledged: bool
    purpose: str = BOUNDED_RAPID_SCAN_PURPOSE
    max_bytes_per_evidence: int = 10_000_000

    def validated(self, *, now: datetime) -> "ValidatedIntakeAuthorization":
        authorization_id = _required(self.authorization_id, label="authorization_id", maximum=256)
        tenant_id = _required(self.tenant_id, label="tenant_id", maximum=64)
        case_ref = _required(self.case_ref, label="case_ref", maximum=512)
        authorized_by_ref = _required(self.authorized_by_ref, label="authorized_by_ref", maximum=512)
        transfer_channel_ref = _required(self.transfer_channel_ref, label="transfer_channel_ref", maximum=1024)
        purpose = _required(self.purpose, label="purpose", maximum=128).upper()
        if purpose != BOUNDED_RAPID_SCAN_PURPOSE:
            raise IntakeAuthorizationError("intake authorization purpose is not permitted for pilot capture")

        if not isinstance(now, datetime) or now.tzinfo is None:
            raise IntakeAuthorizationError("intake authorization validation clock must include timezone")
        observed_now = now.astimezone(timezone.utc)
        authorized_at = _aware(self.authorized_at, label="authorized_at")
        expires_at = _aware(self.expires_at, label="expires_at")
        retain_until = _aware(
            self.minimum_immutable_retention_until,
            label="minimum_immutable_retention_until",
        )
        if authorized_at > observed_now:
            raise IntakeAuthorizationError("intake authorization is not yet effective")
        if expires_at < observed_now:
            raise IntakeAuthorizationError("intake authorization has expired")
        if expires_at < authorized_at:
            raise IntakeAuthorizationError("intake authorization expiry precedes authorization")
        if retain_until <= observed_now:
            raise IntakeAuthorizationError("intake authorization retention is already expired")
        if not self.immutable_retention_acknowledged:
            raise IntakeAuthorizationError("immutable retention must be explicitly acknowledged before capture")

        data_terms_state = _required(self.data_terms_state, label="data_terms_state", maximum=64).upper()
        if data_terms_state not in ALLOWED_DATA_TERMS_STATES:
            raise IntakeAuthorizationError("intake data terms are not cleared")

        roles = tuple(dict.fromkeys(str(role or "").strip().lower() for role in self.evidence_roles))
        if not roles or any(role not in ROLE_SOURCE_TYPES for role in roles):
            raise IntakeAuthorizationError("intake authorization evidence roles are invalid")
        if not isinstance(self.max_bytes_per_evidence, int) or not (1 <= self.max_bytes_per_evidence <= 100_000_000):
            raise IntakeAuthorizationError("intake authorization byte limit is invalid")

        scope = {
            "authorization_id": authorization_id,
            "tenant_id": tenant_id,
            "case_ref": case_ref,
            "purpose": purpose,
            "authorized_at": authorized_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "minimum_immutable_retention_until": retain_until.isoformat(),
            "evidence_roles": list(roles),
            "data_terms_state": data_terms_state,
            "immutable_retention_acknowledged": True,
            "max_bytes_per_evidence": self.max_bytes_per_evidence,
            "authorized_by_sha256": _sha256_text(authorized_by_ref),
            "transfer_channel_sha256": _sha256_text(transfer_channel_ref),
        }
        scope_sha256 = hashlib.sha256(canonical_json_bytes(scope)).hexdigest()
        return ValidatedIntakeAuthorization(
            authorization_id=authorization_id,
            tenant_id=tenant_id,
            case_ref=case_ref,
            purpose=purpose,
            authorized_at=authorized_at,
            expires_at=expires_at,
            minimum_immutable_retention_until=retain_until,
            evidence_roles=roles,
            data_terms_state=data_terms_state,
            max_bytes_per_evidence=self.max_bytes_per_evidence,
            authorized_by_sha256=scope["authorized_by_sha256"],
            transfer_channel_sha256=scope["transfer_channel_sha256"],
            scope_sha256=scope_sha256,
        )


@dataclass(frozen=True)
class ValidatedIntakeAuthorization:
    authorization_id: str
    tenant_id: str
    case_ref: str
    purpose: str
    authorized_at: datetime
    expires_at: datetime
    minimum_immutable_retention_until: datetime
    evidence_roles: tuple[str, ...]
    data_terms_state: str
    max_bytes_per_evidence: int
    authorized_by_sha256: str
    transfer_channel_sha256: str
    scope_sha256: str

    def metadata(self) -> dict[str, Any]:
        return {
            "intake_authorization_id": self.authorization_id,
            "intake_authorization_scope_sha256": self.scope_sha256,
            "intake_case_ref": self.case_ref,
            "intake_purpose": self.purpose,
            "intake_authorized_at": self.authorized_at.isoformat(),
            "intake_authorization_expires_at": self.expires_at.isoformat(),
            "intake_minimum_immutable_retention_until": self.minimum_immutable_retention_until.isoformat(),
            "intake_data_terms_state": self.data_terms_state,
            "intake_immutable_retention_acknowledged": True,
            "intake_authorized_by_sha256": self.authorized_by_sha256,
            "intake_transfer_channel_sha256": self.transfer_channel_sha256,
            "intake_max_bytes_per_evidence": self.max_bytes_per_evidence,
        }


def capture_authorized_original_evidence(
    *,
    authorization: IntakeAuthorization,
    evidence_role: str,
    original_store: OriginalEvidenceStore,
    evidence_id: str,
    identity: CaptureIdentity,
    source_ref: str,
    content: bytes,
    content_type: str,
    source_authentication: SourceAuthenticationReceipt,
    effective_at: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> SecureCaptureResult:
    now = clock()
    validated = authorization.validated(now=now)
    role = str(evidence_role or "").strip().lower()
    if role not in validated.evidence_roles:
        raise IntakeAuthorizationError("evidence role is outside authorized intake scope")
    if identity.tenant_id.strip() != validated.tenant_id:
        raise IntakeAuthorizationError("capture identity tenant does not match intake authorization")
    if not evidence_id.startswith(f"{validated.tenant_id}:"):
        raise IntakeAuthorizationError("evidence_id is outside authorized tenant namespace")
    if not isinstance(content, bytes) or len(content) > validated.max_bytes_per_evidence:
        raise IntakeAuthorizationError("evidence exceeds authorized intake byte limit")

    caller_metadata = dict(metadata or {})
    if any(str(key).startswith("intake_") for key in caller_metadata):
        raise IntakeAuthorizationError("caller metadata cannot override intake authorization bindings")
    authorization_metadata = validated.metadata()
    authorization_metadata["intake_evidence_role"] = role

    captured = capture_original_evidence(
        original_store=original_store,
        evidence_id=evidence_id,
        identity=identity,
        source_type=ROLE_SOURCE_TYPES[role],
        source_ref=source_ref,
        content=content,
        content_type=content_type,
        source_authentication=source_authentication,
        effective_at=effective_at,
        retention_until=validated.minimum_immutable_retention_until.isoformat(),
        legal_hold=False,
        metadata={**caller_metadata, **authorization_metadata},
        clock=lambda: now,
    )
    proof_metadata = captured.evidence.metadata
    for key, expected in authorization_metadata.items():
        if proof_metadata.get(key) != expected:
            raise IntakeAuthorizationError("secure capture lost intake authorization binding")
    return captured
