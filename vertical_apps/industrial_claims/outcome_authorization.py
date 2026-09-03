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


class OutcomeAuthorizationError(ValueError):
    pass


DOCUMENTED_FINAL_OUTCOME_PURPOSE = "DOCUMENTED_FINAL_OUTCOME_RECORDING"
ALLOWED_DATA_TERMS_STATES = {"NOT_REQUIRED", "SIGNED"}


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise OutcomeAuthorizationError(f"invalid outcome authorization {label}")
    return text


def _aware(value: object, *, label: str) -> datetime:
    text = _required(value, label=label, maximum=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeAuthorizationError(f"invalid outcome authorization {label}") from exc
    if parsed.tzinfo is None:
        raise OutcomeAuthorizationError(f"outcome authorization {label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_digest(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise OutcomeAuthorizationError(f"invalid outcome authorization {label}")
    return text


def _byte_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= 100_000_000):
        raise OutcomeAuthorizationError("outcome authorization byte limit is invalid")
    return value


def recompute_outcome_authorization_scope_sha256(
    metadata: Mapping[str, Any],
    *,
    tenant_id: str,
) -> str:
    """Recompute persisted outcome-authorization scope without requiring it to be live now."""
    tenant = _required(tenant_id, label="tenant_id", maximum=64)
    authorization_id = _required(metadata.get("outcome_authorization_id"), label="authorization_id", maximum=256)
    finding_id = _required(metadata.get("outcome_finding_id"), label="finding_id", maximum=2048)
    if not finding_id.startswith(f"{tenant}:"):
        raise OutcomeAuthorizationError("outcome finding_id is outside authorized tenant namespace")
    purpose = _required(metadata.get("outcome_purpose"), label="purpose", maximum=128).upper()
    if purpose != DOCUMENTED_FINAL_OUTCOME_PURPOSE:
        raise OutcomeAuthorizationError("outcome authorization purpose is not permitted")
    authorized_at = _aware(metadata.get("outcome_authorized_at"), label="authorized_at")
    expires_at = _aware(metadata.get("outcome_authorization_expires_at"), label="expires_at")
    retain_until = _aware(
        metadata.get("outcome_minimum_immutable_retention_until"),
        label="minimum_immutable_retention_until",
    )
    if expires_at < authorized_at:
        raise OutcomeAuthorizationError("outcome authorization expiry precedes authorization")
    if not (
        metadata.get("outcome_immutable_retention_acknowledged") is True
        or str(metadata.get("outcome_immutable_retention_acknowledged") or "").strip().lower() == "true"
    ):
        raise OutcomeAuthorizationError("immutable retention was not acknowledged")
    data_terms_state = _required(metadata.get("outcome_data_terms_state"), label="data_terms_state", maximum=64).upper()
    if data_terms_state not in ALLOWED_DATA_TERMS_STATES:
        raise OutcomeAuthorizationError("outcome data terms are not cleared")
    max_bytes = _byte_limit(metadata.get("outcome_max_bytes"))
    authorized_by_sha256 = _sha256_digest(
        metadata.get("outcome_authorized_by_sha256"),
        label="authorized_by_sha256",
    )
    transfer_channel_sha256 = _sha256_digest(
        metadata.get("outcome_transfer_channel_sha256"),
        label="transfer_channel_sha256",
    )
    scope = {
        "authorization_id": authorization_id,
        "tenant_id": tenant,
        "finding_id": finding_id,
        "purpose": purpose,
        "authorized_at": authorized_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "minimum_immutable_retention_until": retain_until.isoformat(),
        "data_terms_state": data_terms_state,
        "immutable_retention_acknowledged": True,
        "max_bytes": max_bytes,
        "authorized_by_sha256": authorized_by_sha256,
        "transfer_channel_sha256": transfer_channel_sha256,
    }
    return hashlib.sha256(canonical_json_bytes(scope)).hexdigest()


@dataclass(frozen=True)
class OutcomeEvidenceAuthorization:
    authorization_id: str
    tenant_id: str
    finding_id: str
    authorized_by_ref: str
    authorized_at: str
    expires_at: str
    minimum_immutable_retention_until: str
    transfer_channel_ref: str
    data_terms_state: str
    immutable_retention_acknowledged: bool
    purpose: str = DOCUMENTED_FINAL_OUTCOME_PURPOSE
    max_bytes: int = 10_000_000

    def validated(self, *, now: datetime) -> "ValidatedOutcomeAuthorization":
        authorization_id = _required(self.authorization_id, label="authorization_id", maximum=256)
        tenant_id = _required(self.tenant_id, label="tenant_id", maximum=64)
        finding_id = _required(self.finding_id, label="finding_id", maximum=2048)
        if not finding_id.startswith(f"{tenant_id}:"):
            raise OutcomeAuthorizationError("outcome finding_id is outside authorized tenant namespace")
        authorized_by_ref = _required(self.authorized_by_ref, label="authorized_by_ref", maximum=512)
        transfer_channel_ref = _required(self.transfer_channel_ref, label="transfer_channel_ref", maximum=1024)
        purpose = _required(self.purpose, label="purpose", maximum=128).upper()
        if purpose != DOCUMENTED_FINAL_OUTCOME_PURPOSE:
            raise OutcomeAuthorizationError("outcome authorization purpose is not permitted")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise OutcomeAuthorizationError("outcome authorization validation clock must include timezone")
        observed_now = now.astimezone(timezone.utc)
        authorized_at = _aware(self.authorized_at, label="authorized_at")
        expires_at = _aware(self.expires_at, label="expires_at")
        retain_until = _aware(
            self.minimum_immutable_retention_until,
            label="minimum_immutable_retention_until",
        )
        if authorized_at > observed_now:
            raise OutcomeAuthorizationError("outcome authorization is not yet effective")
        if expires_at < observed_now:
            raise OutcomeAuthorizationError("outcome authorization has expired")
        if expires_at < authorized_at:
            raise OutcomeAuthorizationError("outcome authorization expiry precedes authorization")
        if retain_until <= observed_now:
            raise OutcomeAuthorizationError("outcome authorization retention is already expired")
        if not self.immutable_retention_acknowledged:
            raise OutcomeAuthorizationError("immutable retention must be explicitly acknowledged")
        data_terms_state = _required(self.data_terms_state, label="data_terms_state", maximum=64).upper()
        if data_terms_state not in ALLOWED_DATA_TERMS_STATES:
            raise OutcomeAuthorizationError("outcome data terms are not cleared")
        max_bytes = _byte_limit(self.max_bytes)

        scope = {
            "authorization_id": authorization_id,
            "tenant_id": tenant_id,
            "finding_id": finding_id,
            "purpose": purpose,
            "authorized_at": authorized_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "minimum_immutable_retention_until": retain_until.isoformat(),
            "data_terms_state": data_terms_state,
            "immutable_retention_acknowledged": True,
            "max_bytes": max_bytes,
            "authorized_by_sha256": _sha256_text(authorized_by_ref),
            "transfer_channel_sha256": _sha256_text(transfer_channel_ref),
        }
        return ValidatedOutcomeAuthorization(
            authorization_id=authorization_id,
            tenant_id=tenant_id,
            finding_id=finding_id,
            purpose=purpose,
            authorized_at=authorized_at,
            expires_at=expires_at,
            minimum_immutable_retention_until=retain_until,
            data_terms_state=data_terms_state,
            max_bytes=max_bytes,
            authorized_by_sha256=scope["authorized_by_sha256"],
            transfer_channel_sha256=scope["transfer_channel_sha256"],
            scope_sha256=hashlib.sha256(canonical_json_bytes(scope)).hexdigest(),
        )


@dataclass(frozen=True)
class ValidatedOutcomeAuthorization:
    authorization_id: str
    tenant_id: str
    finding_id: str
    purpose: str
    authorized_at: datetime
    expires_at: datetime
    minimum_immutable_retention_until: datetime
    data_terms_state: str
    max_bytes: int
    authorized_by_sha256: str
    transfer_channel_sha256: str
    scope_sha256: str

    def metadata(self) -> dict[str, Any]:
        return {
            "outcome_authorization_id": self.authorization_id,
            "outcome_authorization_scope_sha256": self.scope_sha256,
            "outcome_finding_id": self.finding_id,
            "outcome_purpose": self.purpose,
            "outcome_authorized_at": self.authorized_at.isoformat(),
            "outcome_authorization_expires_at": self.expires_at.isoformat(),
            "outcome_minimum_immutable_retention_until": self.minimum_immutable_retention_until.isoformat(),
            "outcome_data_terms_state": self.data_terms_state,
            "outcome_immutable_retention_acknowledged": True,
            "outcome_authorized_by_sha256": self.authorized_by_sha256,
            "outcome_transfer_channel_sha256": self.transfer_channel_sha256,
            "outcome_max_bytes": self.max_bytes,
        }


def capture_authorized_outcome_evidence(
    *,
    authorization: OutcomeEvidenceAuthorization,
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
    if identity.tenant_id.strip() != validated.tenant_id:
        raise OutcomeAuthorizationError("capture identity tenant does not match outcome authorization")
    if not evidence_id.startswith(f"{validated.tenant_id}:"):
        raise OutcomeAuthorizationError("outcome evidence_id is outside authorized tenant namespace")
    if not isinstance(content, bytes) or not content or len(content) > validated.max_bytes:
        raise OutcomeAuthorizationError("outcome evidence exceeds authorized byte limit")

    caller_metadata = dict(metadata or {})
    if any(str(key).startswith("outcome_") for key in caller_metadata):
        raise OutcomeAuthorizationError("caller metadata cannot override outcome authorization bindings")
    if "verification_state" in caller_metadata:
        raise OutcomeAuthorizationError("caller metadata cannot override outcome verification state")
    authorization_metadata = validated.metadata()
    captured = capture_original_evidence(
        original_store=original_store,
        evidence_id=evidence_id,
        identity=identity,
        source_type="recovery_outcome_evidence",
        source_ref=source_ref,
        content=content,
        content_type=content_type,
        source_authentication=source_authentication,
        effective_at=effective_at,
        retention_until=validated.minimum_immutable_retention_until.isoformat(),
        legal_hold=False,
        metadata={
            **caller_metadata,
            **authorization_metadata,
            "verification_state": "CONTENT_HASHED",
        },
        clock=lambda: now,
    )
    for key, expected in authorization_metadata.items():
        if captured.evidence.metadata.get(key) != expected:
            raise OutcomeAuthorizationError("secure capture lost outcome authorization binding")
    if captured.evidence.metadata.get("verification_state") != "CONTENT_HASHED":
        raise OutcomeAuthorizationError("secure capture lost content-hash verification state")
    if recompute_outcome_authorization_scope_sha256(
        captured.evidence.metadata,
        tenant_id=validated.tenant_id,
    ) != validated.scope_sha256:
        raise OutcomeAuthorizationError("secure capture outcome authorization scope is not independently reproducible")
    return captured