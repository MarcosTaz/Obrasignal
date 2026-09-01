from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from factory_cloud.assurance_kernel import EvidenceEnvelope
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore, verify_original_receipt


_VERIFIED_SOURCE_STATES = {"VERIFIED", "VALID", "DKIM_VALID", "SIGNATURE_VALID", "API_VERIFIED", "DIRECT_SOURCE_CAPTURE"}
_STRONG_AMR = {"mfa", "webauthn", "passkey", "hwk", "fido", "fido2"}


def _server_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_datetime(value: datetime, *, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class CaptureIdentity:
    tenant_id: str
    actor_id: str
    subject: str
    amr: tuple[str, ...] = ()
    auth_time: str | None = None
    session_ref: str | None = None
    device_ref: str | None = None
    request_ref: str | None = None

    @property
    def strong_authentication(self) -> bool:
        return bool({item.strip().lower() for item in self.amr} & _STRONG_AMR)


@dataclass(frozen=True)
class SourceAuthenticationReceipt:
    state: str
    scheme: str
    provider: str
    provider_ref: str | None = None
    checked_at: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        state = str(self.state or "").strip().upper()
        if not state or not str(self.scheme or "").strip() or not str(self.provider or "").strip():
            raise ValueError("source authentication state, scheme and provider are required")
        if state in _VERIFIED_SOURCE_STATES:
            if not self.provider_ref or not self.checked_at:
                raise ValueError("verified source authentication requires provider reference and checked_at")
            parsed = _parse_aware(self.checked_at, label="source authentication checked_at")
            if parsed is None:
                raise ValueError("verified source authentication requires checked_at")

    @property
    def verified(self) -> bool:
        return self.state.strip().upper() in _VERIFIED_SOURCE_STATES


@dataclass(frozen=True)
class SecureCaptureResult:
    evidence: EvidenceEnvelope
    original_receipt_ref: str
    delayed_evidence: bool
    strong_identity: bool


def _parse_aware(value: str | None, *, label: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _immutability_state(*, retention_mode: str, legal_hold: bool) -> str:
    """Describe storage strength without upgrading governance retention to WORM."""
    mode = str(retention_mode or "").strip().upper()
    if mode == "COMPLIANCE":
        return "WORM_LOCKED"
    if mode == "LEGAL_HOLD" or legal_hold:
        return "LEGAL_HOLD"
    if mode == "GOVERNANCE":
        return "GOVERNANCE_RETENTION"
    return "UNVERIFIED"


def capture_original_evidence(
    *,
    original_store: OriginalEvidenceStore,
    evidence_id: str,
    identity: CaptureIdentity,
    source_type: str,
    source_ref: str,
    content: bytes,
    content_type: str,
    source_authentication: SourceAuthenticationReceipt,
    effective_at: str | None = None,
    retention_until: str | None = None,
    legal_hold: bool = False,
    metadata: Mapping[str, Any] | None = None,
    clock: Callable[[], datetime] = _server_now,
) -> SecureCaptureResult:
    if not isinstance(content, bytes) or not content:
        raise ValueError("secure evidence capture requires non-empty original bytes")
    if not evidence_id.strip() or not source_type.strip() or not source_ref.strip() or not content_type.strip():
        raise ValueError("secure evidence capture identity and source metadata are required")
    if identity.tenant_id.strip() == "" or identity.actor_id.strip() == "" or identity.subject.strip() == "":
        raise ValueError("secure evidence capture requires authenticated tenant/actor/subject")

    # first_seen is deliberately generated inside the trusted capture boundary.
    # User/request metadata may declare effective_at, but cannot override first_seen.
    first_seen = _aware_datetime(clock(), label="secure capture clock")
    effective = _parse_aware(effective_at, label="effective_at")
    delayed = effective is not None and effective < first_seen
    digests = dual_digest(content)
    receipt = original_store.put_immutable(
        tenant_id=identity.tenant_id,
        evidence_id=evidence_id,
        content=content,
        content_type=content_type,
        retention_until=retention_until,
        legal_hold=legal_hold,
        metadata={
            "source_type": source_type,
            "source_ref": source_ref,
            "capture_actor": identity.actor_id,
            "capture_subject": identity.subject,
            **dict(metadata or {}),
        },
    )
    receipt_validation = verify_original_receipt(content, receipt)
    if not receipt_validation["valid"]:
        raise ValueError("immutable original store returned a receipt that does not match captured bytes")

    immutability_state = _immutability_state(
        retention_mode=receipt.retention_mode,
        legal_hold=receipt.legal_hold,
    )
    proof_metadata = {
        **dict(metadata or {}),
        "content_sha512": digests["sha512"],
        "content_size_bytes": digests["byte_length"],
        "content_type": content_type,
        "capture_mode": "DIRECT_SECURE_ORIGINAL_CAPTURE",
        "raw_content_persisted": "true",
        "proof_integrity_sealed": True,
        "immutability": immutability_state,
        "worm_lock_verified": immutability_state == "WORM_LOCKED",
        "first_seen_at": first_seen.isoformat(),
        "effective_at": effective.isoformat() if effective is not None else None,
        "delayed_evidence": delayed,
        "source_authentication": source_authentication.state.strip().upper(),
        "source_authentication_scheme": source_authentication.scheme,
        "source_authentication_provider": source_authentication.provider,
        "source_authentication_provider_ref": source_authentication.provider_ref,
        "source_authentication_checked_at": source_authentication.checked_at,
        "identity_actor_id": identity.actor_id,
        "identity_subject": identity.subject,
        "identity_amr": list(identity.amr),
        "identity_strong_authentication": identity.strong_authentication,
        "auth_time": identity.auth_time,
        "session_ref": identity.session_ref,
        "device_ref": identity.device_ref,
        "request_ref": identity.request_ref,
        "original_store_provider": receipt.provider,
        "original_object_ref": receipt.object_ref,
        "original_version_ref": receipt.version_ref,
        "original_provider_receipt_ref": receipt.provider_receipt_ref,
        "original_retention_mode": receipt.retention_mode,
        "original_retention_until": receipt.retention_until,
        "original_legal_hold": receipt.legal_hold,
        "time_attestation": "LOCAL_SERVER_ONLY",
    }
    evidence = EvidenceEnvelope.create(
        evidence_id=evidence_id,
        tenant_id=identity.tenant_id,
        source_type=source_type,
        source_ref=source_ref,
        content=content,
        metadata=proof_metadata,
        received_at=first_seen.isoformat(),
    )
    if evidence.content_hash != digests["sha256"]:
        raise ValueError("secure capture SHA-256 mismatch")
    return SecureCaptureResult(
        evidence=evidence,
        original_receipt_ref=receipt.provider_receipt_ref,
        delayed_evidence=delayed,
        strong_identity=identity.strong_authentication,
    )
