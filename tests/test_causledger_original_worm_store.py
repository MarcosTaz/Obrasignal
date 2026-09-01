from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from vertical_apps.industrial_claims.original_worm_store import OriginalWormStoreError, WormOriginalEvidenceStore
from vertical_apps.industrial_claims.worm_lock_provider import WormObjectHead, WormWriteReceipt


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class Backend:
    name = "fake-object-lock"

    def __init__(self, *, locked=True, mode="COMPLIANCE", shorten=False, readback=None, metadata_override=None):
        self.locked = locked
        self.mode = mode
        self.shorten = shorten
        self.readback_override = readback
        self.metadata_override = metadata_override
        self.payload = None
        self.object_key = None
        self.version_id = "version-1"
        self.retain_until = None
        self.metadata = None

    def put_immutable(self, *, object_key, payload, content_sha256, retention_mode, retain_until, metadata):
        self.payload = payload
        self.object_key = object_key
        self.content_sha256 = content_sha256
        self.retain_until = retain_until
        self.metadata = dict(metadata)
        return WormWriteReceipt(object_key=object_key, version_id=self.version_id, provider_ref="provider-receipt-1")

    def head_version(self, *, object_key, version_id):
        retain = self.retain_until - timedelta(days=1) if self.shorten else self.retain_until
        metadata = dict(self.metadata)
        if self.metadata_override:
            metadata.update(self.metadata_override)
        return WormObjectHead(
            object_key=object_key,
            version_id=version_id,
            content_sha256=self.content_sha256,
            content_length=len(self.payload),
            object_lock_enabled=self.locked,
            retention_mode=self.mode,
            retain_until=retain.isoformat(),
            provider_metadata=metadata,
        )

    def read_version(self, *, object_key, version_id):
        return self.payload if self.readback_override is None else self.readback_override


def _store(backend):
    return WormOriginalEvidenceStore(
        backend=backend,
        minimum_retention=timedelta(days=365),
        clock=lambda: NOW,
    )


def _put(store):
    return store.put_immutable(
        tenant_id="tenant-a",
        evidence_id="tenant-a:case:x:commercial-basis",
        content=b"confidential original customer document",
        content_type="application/pdf",
        retention_until=(NOW + timedelta(days=366)).isoformat(),
        legal_hold=False,
        metadata={
            "source_ref": "customer-po-12345.pdf",
            "capture_actor": "client@example.com",
            "capture_subject": "subject-123",
        },
    )


def test_original_store_requires_compliance_lock_and_exact_version_readback():
    backend = Backend()
    receipt = _put(_store(backend))
    assert receipt.retention_mode == "COMPLIANCE"
    assert receipt.object_ref.startswith("causledger/originals/")
    assert receipt.version_ref == "version-1"
    assert receipt.provider_receipt_ref == "provider-receipt-1"
    assert receipt.metadata["exact_version_read_back"] is True
    assert receipt.metadata["external_object_metadata_contains_plain_source_ref"] is False
    assert "customer-po-12345.pdf" not in str(backend.metadata)
    assert "client@example.com" not in str(backend.metadata)
    assert "subject-123" not in str(backend.metadata)


@pytest.mark.parametrize(
    "backend,expected",
    [
        (Backend(locked=False), "OBJECT_LOCK_DISABLED"),
        (Backend(mode="GOVERNANCE"), "COMPLIANCE_RETENTION_REQUIRED"),
        (Backend(shorten=True), "PROVIDER_RETENTION_SHORTENED"),
        (Backend(readback=b"different bytes"), "READBACK_DIGEST_OR_LENGTH_MISMATCH"),
    ],
)
def test_original_store_fails_closed_on_provider_verification_errors(backend, expected):
    with pytest.raises(OriginalWormStoreError, match=expected):
        _put(_store(backend))


def test_original_store_rejects_legal_hold_claim_it_cannot_set():
    store = _store(Backend())
    with pytest.raises(OriginalWormStoreError, match="legal hold"):
        store.put_immutable(
            tenant_id="tenant-a",
            evidence_id="e1",
            content=b"original",
            content_type="application/pdf",
            retention_until=(NOW + timedelta(days=366)).isoformat(),
            legal_hold=True,
            metadata={},
        )


def test_original_store_detects_provider_metadata_binding_substitution():
    backend = Backend(metadata_override={"causledger_content_sha256": "0" * 64})
    with pytest.raises(OriginalWormStoreError, match="metadata binding mismatch"):
        _put(_store(backend))
