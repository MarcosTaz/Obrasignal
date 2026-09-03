from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

from vertical_apps.industrial_claims.s3_worm_backend import S3ObjectLockBackend, S3WormBackendError


NOW = datetime.now(timezone.utc)


class FakeS3:
    def __init__(self):
        self.put = None

    def get_bucket_versioning(self, **kwargs):
        return {"Status": "Enabled"}

    def get_object_lock_configuration(self, **kwargs):
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}

    def put_object(self, **kwargs):
        self.put = kwargs
        return {"VersionId": "v-1"}

    def head_object(self, **kwargs):
        return {
            "VersionId": "v-1",
            "Metadata": {"causledger_content_sha256": "a" * 64},
            "ContentLength": 3,
            "ObjectLockMode": "COMPLIANCE",
            "ObjectLockRetainUntilDate": NOW + timedelta(days=365),
        }

    def get_object(self, **kwargs):
        return {"VersionId": "v-1", "Body": BytesIO(b"abc")}


def test_bucket_preflight_requires_versioning_and_object_lock():
    client = FakeS3()
    backend = S3ObjectLockBackend(client=client, bucket="certactum-worm")
    status = backend.verify_bucket_controls()
    assert status["versioning_enabled"] is True
    assert status["object_lock_enabled"] is True


def test_put_forces_compliance_checksum_encryption_and_future_retention():
    client = FakeS3()
    backend = S3ObjectLockBackend(client=client, bucket="certactum-worm")
    payload = b"abc"
    import hashlib
    digest = hashlib.sha256(payload).hexdigest()
    receipt = backend.put_immutable(
        object_key="tenant/evidence",
        payload=payload,
        content_sha256=digest,
        retention_mode="COMPLIANCE",
        retain_until=NOW + timedelta(days=365),
        metadata={"causledger_content_sha256": digest},
    )
    assert receipt.version_id == "v-1"
    assert client.put["ObjectLockMode"] == "COMPLIANCE"
    assert client.put["ServerSideEncryption"] == "AES256"
    assert client.put["ChecksumSHA256"]


def test_governance_mode_is_rejected_before_provider_write():
    client = FakeS3()
    backend = S3ObjectLockBackend(client=client, bucket="certactum-worm")
    with pytest.raises(S3WormBackendError, match="COMPLIANCE"):
        backend.put_immutable(
            object_key="tenant/evidence",
            payload=b"abc",
            content_sha256="a" * 64,
            retention_mode="GOVERNANCE",
            retain_until=NOW + timedelta(days=365),
            metadata={},
        )
    assert client.put is None


def test_head_and_read_are_exact_version_scoped():
    client = FakeS3()
    backend = S3ObjectLockBackend(client=client, bucket="certactum-worm")
    head = backend.head_version(object_key="k", version_id="v-1")
    assert head.version_id == "v-1"
    assert head.retention_mode == "COMPLIANCE"
    assert head.object_lock_enabled is True
    assert backend.read_version(object_key="k", version_id="v-1") == b"abc"
