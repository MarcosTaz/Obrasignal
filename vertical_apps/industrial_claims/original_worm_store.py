from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore, OriginalObjectReceipt
from vertical_apps.industrial_claims.worm_lock_provider import WormObjectBackend


class OriginalWormStoreError(RuntimeError):
    pass


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise OriginalWormStoreError(f"invalid original-store {label}")
    return text


def _aware(value: object, *, label: str) -> datetime:
    text = _required(value, label=label, maximum=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OriginalWormStoreError(f"invalid original-store {label}") from exc
    if parsed.tzinfo is None:
        raise OriginalWormStoreError(f"original-store {label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class WormOriginalEvidenceStore(OriginalEvidenceStore):
    """Persist exact original bytes in versioned COMPLIANCE WORM storage.

    The external object metadata contains only hashes and bounded technical facts;
    source references, actor identities and other case metadata are never copied in
    clear. A write is accepted only after version-specific HEAD and exact byte
    read-back prove that the immutable object contains the captured bytes.
    """

    def __init__(
        self,
        *,
        backend: WormObjectBackend,
        minimum_retention: timedelta = timedelta(days=365),
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        self.backend = backend
        self.name = _required(getattr(backend, "name", ""), label="backend name", maximum=128)
        if minimum_retention < timedelta(days=1):
            raise OriginalWormStoreError("minimum original retention must be at least one day")
        self.minimum_retention = minimum_retention
        self.clock = clock

    @staticmethod
    def _object_key(*, tenant_id: str, evidence_id: str, sha256: str) -> str:
        return (
            "causledger/originals/"
            f"{_hash_text(tenant_id)[:24]}/{_hash_text(evidence_id)[:24]}/{sha256}"
        )

    @staticmethod
    def _expected_object_prefix(*, tenant_id: str, evidence_id: str) -> str:
        return (
            "causledger/originals/"
            f"{_hash_text(tenant_id)[:24]}/{_hash_text(evidence_id)[:24]}/"
        )

    def put_immutable(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        content: bytes,
        content_type: str,
        retention_until: str | None,
        legal_hold: bool,
        metadata: Mapping[str, Any],
    ) -> OriginalObjectReceipt:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        evidence = _required(evidence_id, label="evidence_id")
        media_type = _required(content_type, label="content_type", maximum=256)
        if not isinstance(content, bytes) or not content:
            raise OriginalWormStoreError("original-store requires non-empty bytes")
        if legal_hold:
            raise OriginalWormStoreError("legal hold cannot be asserted through a backend contract that cannot set it")

        now = self.clock().astimezone(timezone.utc)
        if retention_until is None:
            retain_until = now + self.minimum_retention
        else:
            retain_until = _aware(retention_until, label="retention_until")
        if retain_until < now + self.minimum_retention:
            raise OriginalWormStoreError("requested original retention is below configured minimum")

        digests = dual_digest(content)
        object_key = self._object_key(tenant_id=tenant, evidence_id=evidence, sha256=digests["sha256"])
        source_ref = str(metadata.get("source_ref") or "")
        actor = str(metadata.get("capture_actor") or "")
        subject = str(metadata.get("capture_subject") or "")
        provider_metadata = {
            "causledger_tenant_sha256": _hash_text(tenant),
            "causledger_evidence_sha256": _hash_text(evidence),
            "causledger_content_sha256": digests["sha256"],
            "causledger_content_type_sha256": _hash_text(media_type),
            "causledger_source_ref_sha256": _hash_text(source_ref) if source_ref else "",
            "causledger_capture_actor_sha256": _hash_text(actor) if actor else "",
            "causledger_capture_subject_sha256": _hash_text(subject) if subject else "",
        }
        try:
            write = self.backend.put_immutable(
                object_key=object_key,
                payload=content,
                content_sha256=digests["sha256"],
                retention_mode="COMPLIANCE",
                retain_until=retain_until,
                metadata=provider_metadata,
            )
            if write.object_key != object_key:
                raise OriginalWormStoreError("original-store provider changed object key")
            head = self.backend.head_version(object_key=object_key, version_id=write.version_id)
            readback = self.backend.read_version(object_key=object_key, version_id=write.version_id)
        except OriginalWormStoreError:
            raise
        except Exception as exc:
            raise OriginalWormStoreError("immutable original provider operation failed") from exc

        errors: list[str] = []
        if head.object_key != object_key:
            errors.append("OBJECT_KEY_MISMATCH")
        if head.version_id != write.version_id:
            errors.append("VERSION_ID_MISMATCH")
        if head.content_sha256.lower() != digests["sha256"]:
            errors.append("PROVIDER_SHA256_MISMATCH")
        if head.content_length != len(content):
            errors.append("CONTENT_LENGTH_MISMATCH")
        if not head.object_lock_enabled:
            errors.append("OBJECT_LOCK_DISABLED")
        if head.retention_mode.upper() != "COMPLIANCE":
            errors.append("COMPLIANCE_RETENTION_REQUIRED")
        try:
            observed_until = _aware(head.retain_until, label="provider_retain_until")
        except OriginalWormStoreError:
            errors.append("PROVIDER_RETENTION_INVALID")
            observed_until = now
        if observed_until < retain_until:
            errors.append("PROVIDER_RETENTION_SHORTENED")
        if not isinstance(readback, bytes):
            errors.append("READBACK_NOT_BYTES")
        else:
            observed = dual_digest(readback)
            if observed != digests:
                errors.append("READBACK_DIGEST_OR_LENGTH_MISMATCH")
            if readback != content:
                errors.append("READBACK_BYTES_MISMATCH")
        if errors:
            raise OriginalWormStoreError("immutable original verification failed: " + ",".join(errors))

        provider_head_metadata = dict(head.provider_metadata or {})
        for key, expected in provider_metadata.items():
            if key in provider_head_metadata and str(provider_head_metadata[key]) != expected:
                raise OriginalWormStoreError("immutable original provider metadata binding mismatch")

        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=object_key,
            version_ref=write.version_id,
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode="COMPLIANCE",
            retention_until=head.retain_until,
            legal_hold=False,
            provider_receipt_ref=write.provider_ref,
            metadata={
                "object_lock_enabled": True,
                "exact_version_read_back": True,
                "exact_original_bytes_rehashed": True,
                "external_object_metadata_contains_plain_source_ref": False,
                "external_object_metadata_contains_plain_actor_identity": False,
                "provider_metadata": provider_head_metadata,
            },
        )

    def read_immutable_version(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        object_ref: str,
        version_ref: str,
    ) -> bytes:
        """Read one exact immutable version and re-prove its tenant/evidence binding."""
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        evidence = _required(evidence_id, label="evidence_id")
        object_key = _required(object_ref, label="object_ref")
        version = _required(version_ref, label="version_ref")
        expected_prefix = self._expected_object_prefix(tenant_id=tenant, evidence_id=evidence)
        if not object_key.startswith(expected_prefix):
            raise OriginalWormStoreError("immutable original object does not belong to requested tenant/evidence")
        committed_sha256 = object_key[len(expected_prefix):]
        if len(committed_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in committed_sha256.lower()):
            raise OriginalWormStoreError("immutable original object digest binding is invalid")

        try:
            head = self.backend.head_version(object_key=object_key, version_id=version)
            payload = self.backend.read_version(object_key=object_key, version_id=version)
        except Exception as exc:
            raise OriginalWormStoreError("immutable original exact-version retrieval failed") from exc

        errors: list[str] = []
        if head.object_key != object_key:
            errors.append("OBJECT_KEY_MISMATCH")
        if head.version_id != version:
            errors.append("VERSION_ID_MISMATCH")
        if not head.object_lock_enabled:
            errors.append("OBJECT_LOCK_DISABLED")
        if head.retention_mode.upper() != "COMPLIANCE":
            errors.append("COMPLIANCE_RETENTION_REQUIRED")
        if not isinstance(payload, bytes) or not payload:
            errors.append("READBACK_NOT_BYTES")
        else:
            observed_sha256 = hashlib.sha256(payload).hexdigest()
            if observed_sha256 != committed_sha256.lower():
                errors.append("OBJECT_KEY_DIGEST_MISMATCH")
            if observed_sha256 != str(head.content_sha256 or "").strip().lower():
                errors.append("PROVIDER_SHA256_MISMATCH")
            if len(payload) != head.content_length:
                errors.append("CONTENT_LENGTH_MISMATCH")
        if errors:
            raise OriginalWormStoreError("immutable original retrieval verification failed: " + ",".join(errors))
        return payload
