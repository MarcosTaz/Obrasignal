from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol

from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes
from vertical_apps.industrial_claims.proof_providers import ProofProvider, ProofRequest


class WormLockConfigurationError(ValueError):
    pass


class WormLockVerificationError(RuntimeError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _required(value: object, *, label: str, maximum: int = 2048) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise WormLockConfigurationError(f"invalid {label}")
    return text


def _digest(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise WormLockConfigurationError("WORM request digest must be SHA-256 hex")
    return text


def _aware(value: object, *, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WormLockConfigurationError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise WormLockConfigurationError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class WormWriteReceipt:
    object_key: str
    version_id: str
    provider_ref: str

    def __post_init__(self) -> None:
        _required(self.object_key, label="WORM object key", maximum=4096)
        _required(self.version_id, label="WORM version id", maximum=2048)
        _required(self.provider_ref, label="WORM provider reference", maximum=4096)


@dataclass(frozen=True)
class WormObjectHead:
    object_key: str
    version_id: str
    content_sha256: str
    content_length: int
    object_lock_enabled: bool
    retention_mode: str
    retain_until: str
    legal_hold: str | None = None
    provider_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _required(self.object_key, label="WORM object key", maximum=4096)
        _required(self.version_id, label="WORM version id", maximum=2048)
        _digest(self.content_sha256)
        if not isinstance(self.content_length, int) or self.content_length < 0:
            raise WormLockConfigurationError("invalid WORM content length")
        _aware(self.retain_until, label="WORM retain-until")
        if str(self.retention_mode or "").strip().upper() not in {"COMPLIANCE", "GOVERNANCE"}:
            raise WormLockConfigurationError("unsupported WORM retention mode")


class WormObjectBackend(Protocol):
    """Provider adapter for a versioned object store with immutable retention."""

    name: str

    def put_immutable(
        self,
        *,
        object_key: str,
        payload: bytes,
        content_sha256: str,
        retention_mode: str,
        retain_until: datetime,
        metadata: Mapping[str, str],
    ) -> WormWriteReceipt:
        ...

    def head_version(self, *, object_key: str, version_id: str) -> WormObjectHead:
        ...

    def read_version(self, *, object_key: str, version_id: str) -> bytes:
        ...


class EvidenceWormLockProvider(ProofProvider):
    """Verify immutability of one exact evidence object by versioned read-back.

    This provider intentionally cannot make a case-level or manifest-level lock
    stand in for original-document preservation. A verified receipt always names
    one evidence_id and the exact SHA-256 of bytes written, then independently
    re-reads the same immutable object version and hashes those bytes again.
    """

    kind = "WORM_LOCK"

    def __init__(
        self,
        *,
        backend: WormObjectBackend,
        minimum_retention: timedelta = timedelta(days=365),
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        name = _required(getattr(backend, "name", ""), label="WORM backend name", maximum=128)
        if minimum_retention < timedelta(days=1):
            raise WormLockConfigurationError("minimum WORM retention must be at least one day")
        self.backend = backend
        self.name = name
        self.minimum_retention = minimum_retention
        self.clock = clock

    @staticmethod
    def _object_key(*, tenant_id: str, evidence_id: str, digest: str) -> str:
        tenant_hash = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:24]
        evidence_hash = hashlib.sha256(evidence_id.encode("utf-8")).hexdigest()[:24]
        return f"causledger/evidence/{tenant_hash}/{evidence_hash}/{digest}"

    def _nonverified(
        self,
        request: ProofRequest,
        *,
        state: str,
        evidence_id: str | None,
        error_code: str,
        extra: Mapping[str, Any] | None = None,
        provider_ref: str | None = None,
    ) -> ExternalAttestation:
        details: dict[str, Any] = {
            "evidence_id": evidence_id,
            "error_code": error_code,
            "worm_claim_is_fail_closed": True,
            "case_level_lock_does_not_substitute_for_evidence_lock": True,
            **dict(extra or {}),
        }
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=state,
            digest_algorithm="SHA-256",
            digest=request.digest,
            provider_ref=provider_ref,
            details=details,
        )

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        try:
            tenant_id = _required(request.tenant_id, label="tenant_id", maximum=64)
            evidence_id = _required(request.metadata.get("evidence_id"), label="evidence_id")
            digest = _digest(request.digest)
        except WormLockConfigurationError:
            return self._nonverified(
                request,
                state="INVALID_REQUEST",
                evidence_id=str(request.metadata.get("evidence_id") or "") or None,
                error_code="EVIDENCE_ID_OR_DIGEST_INVALID",
            )
        if request.digest_algorithm.upper() != "SHA-256":
            return self._nonverified(
                request, state="INVALID_REQUEST", evidence_id=evidence_id, error_code="SHA256_REQUIRED"
            )
        payload = request.payload
        if not isinstance(payload, bytes) or not payload:
            return self._nonverified(
                request, state="INVALID_REQUEST", evidence_id=evidence_id, error_code="EXACT_ORIGINAL_BYTES_REQUIRED"
            )
        if _sha256(payload) != digest:
            return self._nonverified(
                request, state="INVALID_REQUEST", evidence_id=evidence_id, error_code="PAYLOAD_DIGEST_MISMATCH"
            )

        now = self.clock().astimezone(timezone.utc)
        requested_until_raw = request.metadata.get("retain_until")
        if requested_until_raw is None:
            retain_until = now + self.minimum_retention
        else:
            try:
                retain_until = _aware(requested_until_raw, label="retain_until")
            except WormLockConfigurationError:
                return self._nonverified(
                    request, state="INVALID_REQUEST", evidence_id=evidence_id, error_code="INVALID_RETAIN_UNTIL"
                )
        if retain_until < now + self.minimum_retention:
            return self._nonverified(
                request,
                state="INVALID_REQUEST",
                evidence_id=evidence_id,
                error_code="RETENTION_BELOW_CONFIGURED_MINIMUM",
                extra={"configured_minimum_seconds": int(self.minimum_retention.total_seconds())},
            )

        object_key = self._object_key(tenant_id=tenant_id, evidence_id=evidence_id, digest=digest)
        storage_metadata = {
            "causledger_evidence_id_sha256": hashlib.sha256(evidence_id.encode("utf-8")).hexdigest(),
            "causledger_tenant_id_sha256": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
            "causledger_content_sha256": digest,
        }
        try:
            write = self.backend.put_immutable(
                object_key=object_key,
                payload=payload,
                content_sha256=digest,
                retention_mode="COMPLIANCE",
                retain_until=retain_until,
                metadata=storage_metadata,
            )
            if write.object_key != object_key:
                raise WormLockVerificationError("provider changed WORM object key")
            head = self.backend.head_version(object_key=object_key, version_id=write.version_id)
            readback = self.backend.read_version(object_key=object_key, version_id=write.version_id)
        except Exception as exc:
            return self._nonverified(
                request,
                state="UNAVAILABLE",
                evidence_id=evidence_id,
                error_code="WORM_PROVIDER_OPERATION_FAILED",
                extra={"error_type": type(exc).__name__},
            )

        provider_ref = write.provider_ref
        errors: list[str] = []
        if head.object_key != object_key:
            errors.append("OBJECT_KEY_MISMATCH")
        if head.version_id != write.version_id:
            errors.append("VERSION_ID_MISMATCH")
        if head.content_sha256.lower() != digest:
            errors.append("PROVIDER_CHECKSUM_MISMATCH")
        if head.content_length != len(payload):
            errors.append("CONTENT_LENGTH_MISMATCH")
        if not head.object_lock_enabled:
            errors.append("OBJECT_LOCK_NOT_ENABLED")
        if head.retention_mode.upper() != "COMPLIANCE":
            errors.append("COMPLIANCE_MODE_REQUIRED")
        try:
            observed_until = _aware(head.retain_until, label="provider retain-until")
        except WormLockConfigurationError:
            errors.append("INVALID_PROVIDER_RETAIN_UNTIL")
            observed_until = now
        if observed_until < retain_until:
            errors.append("RETENTION_SHORTENED")
        if not isinstance(readback, bytes) or _sha256(readback) != digest:
            errors.append("READBACK_DIGEST_MISMATCH")
        if readback != payload:
            errors.append("READBACK_BYTES_MISMATCH")

        receipt_material = {
            "backend": self.name,
            "object_key": object_key,
            "version_id": write.version_id,
            "provider_ref": provider_ref,
            "content_sha256": digest,
            "content_length": len(payload),
            "retention_mode": head.retention_mode.upper(),
            "retain_until": head.retain_until,
            "object_lock_enabled": bool(head.object_lock_enabled),
            "legal_hold": head.legal_hold,
            "provider_metadata": dict(head.provider_metadata or {}),
            "readback_sha256": _sha256(readback) if isinstance(readback, bytes) else None,
            "verified_at": now.isoformat(),
        }
        validation_ref = "worm-readback:" + _sha256(canonical_json_bytes(receipt_material))
        if errors:
            return self._nonverified(
                request,
                state="INVALID",
                evidence_id=evidence_id,
                error_code="WORM_READBACK_VERIFICATION_FAILED",
                extra={**receipt_material, "verification_errors": errors},
                provider_ref=provider_ref,
            )

        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="VERIFIED",
            digest_algorithm="SHA-256",
            digest=digest,
            provider_ref=provider_ref,
            issued_at=now.isoformat(),
            validation_ref=validation_ref,
            details={
                "evidence_id": evidence_id,
                **receipt_material,
                "exact_original_bytes_read_back_and_rehashed": True,
                "version_specific_object_lock_verified": True,
                "case_level_lock_does_not_substitute_for_evidence_lock": True,
                "worm_claim_is_fail_closed": True,
            },
        )
