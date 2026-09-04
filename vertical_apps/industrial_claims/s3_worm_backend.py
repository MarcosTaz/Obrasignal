from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Mapping

from vertical_apps.industrial_claims.worm_lock_provider import (
    WormObjectHead,
    WormWriteReceipt,
)


class S3WormBackendError(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise S3WormBackendError("S3 WORM retention timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _sha256_hex(value: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise S3WormBackendError("S3 WORM content digest must be SHA-256 hex")
    return text


class S3ObjectLockBackend:
    """AWS S3 adapter that only writes exact-version COMPLIANCE objects.

    The adapter deliberately refuses GOVERNANCE mode. Every immutable write sends
    the SHA-256 checksum, COMPLIANCE retain-until and private server-side encryption,
    then the VINDORUM WORM layer independently HEADs and reads the exact returned
    VersionId before accepting the evidence.
    """

    name = "AWS_S3_OBJECT_LOCK_COMPLIANCE"

    def __init__(self, *, client, bucket: str, expected_bucket_owner: str | None = None) -> None:
        self.client = client
        self.bucket = str(bucket or "").strip()
        self.expected_bucket_owner = str(expected_bucket_owner or "").strip() or None
        if not self.bucket or len(self.bucket) > 255:
            raise S3WormBackendError("S3 WORM bucket is invalid")

    def _owner(self) -> dict[str, str]:
        return {"ExpectedBucketOwner": self.expected_bucket_owner} if self.expected_bucket_owner else {}

    def verify_bucket_controls(self) -> dict[str, object]:
        """Read-only preflight. Configuration names alone never pass this check."""
        versioning = self.client.get_bucket_versioning(Bucket=self.bucket, **self._owner())
        lock = self.client.get_object_lock_configuration(Bucket=self.bucket, **self._owner())
        enabled = str((lock.get("ObjectLockConfiguration") or {}).get("ObjectLockEnabled") or "").strip()
        if str(versioning.get("Status") or "").strip() != "Enabled":
            raise S3WormBackendError("S3 WORM bucket versioning is not enabled")
        if enabled != "Enabled":
            raise S3WormBackendError("S3 Object Lock is not enabled")
        return {
            "versioning_enabled": True,
            "object_lock_enabled": True,
            "provider": self.name,
        }

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
        if str(retention_mode or "").strip().upper() != "COMPLIANCE":
            raise S3WormBackendError("S3 WORM backend requires COMPLIANCE retention")
        if not isinstance(payload, bytes) or not payload:
            raise S3WormBackendError("S3 WORM payload must be non-empty bytes")
        digest = _sha256_hex(content_sha256)
        observed = hashlib.sha256(payload).hexdigest()
        if observed != digest:
            raise S3WormBackendError("S3 WORM payload digest mismatch")
        retain = _utc(retain_until)
        if retain <= datetime.now(timezone.utc):
            raise S3WormBackendError("S3 WORM retain-until must be in the future")
        checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
        response = self.client.put_object(
            Bucket=self.bucket,
            Key=str(object_key),
            Body=payload,
            ChecksumSHA256=checksum,
            ServerSideEncryption="AES256",
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=retain,
            Metadata={str(k): str(v) for k, v in metadata.items()},
            **self._owner(),
        )
        version_id = str(response.get("VersionId") or "").strip()
        if not version_id or version_id == "null":
            raise S3WormBackendError("S3 immutable write did not return a version id")
        return WormWriteReceipt(
            object_key=str(object_key),
            version_id=version_id,
            provider_ref=f"s3-version:{version_id}",
        )

    def head_version(self, *, object_key: str, version_id: str) -> WormObjectHead:
        response = self.client.head_object(
            Bucket=self.bucket,
            Key=str(object_key),
            VersionId=str(version_id),
            ChecksumMode="ENABLED",
            **self._owner(),
        )
        returned_version = str(response.get("VersionId") or "").strip()
        if returned_version != str(version_id):
            raise S3WormBackendError("S3 returned a different object version")
        metadata = dict(response.get("Metadata") or {})
        digest = str(metadata.get("causledger_content_sha256") or "").strip().lower()
        _sha256_hex(digest)
        retain = response.get("ObjectLockRetainUntilDate")
        if not isinstance(retain, datetime):
            raise S3WormBackendError("S3 object retain-until is missing")
        return WormObjectHead(
            object_key=str(object_key),
            version_id=returned_version,
            content_sha256=digest,
            content_length=int(response.get("ContentLength") or 0),
            object_lock_enabled=str(response.get("ObjectLockMode") or "").upper() in {"COMPLIANCE", "GOVERNANCE"},
            retention_mode=str(response.get("ObjectLockMode") or ""),
            retain_until=_utc(retain).isoformat(),
            legal_hold=str(response.get("ObjectLockLegalHoldStatus") or "").strip() or None,
            provider_metadata=metadata,
        )

    def read_version(self, *, object_key: str, version_id: str) -> bytes:
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=str(object_key),
            VersionId=str(version_id),
            ChecksumMode="ENABLED",
            **self._owner(),
        )
        returned_version = str(response.get("VersionId") or "").strip()
        if returned_version != str(version_id):
            raise S3WormBackendError("S3 returned a different object version")
        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise S3WormBackendError("S3 object body is unavailable")
        payload = body.read()
        if not isinstance(payload, bytes) or not payload:
            raise S3WormBackendError("S3 exact-version readback is empty")
        return payload
