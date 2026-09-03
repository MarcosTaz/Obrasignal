from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import (
    CaptureIdentity,
    SourceAuthenticationReceipt,
    capture_original_evidence,
)


class FakeImmutableStore:
    name = "fake-worm"

    def __init__(self, *, readback_override: bytes | None = None):
        self._stored: dict[tuple[str, str], bytes] = {}
        self.readback_override = readback_override

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        digests = dual_digest(content)
        self._stored[(f"{tenant_id}/{evidence_id}", "v1")] = content
        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=f"{tenant_id}/{evidence_id}",
            version_ref="v1",
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode="COMPLIANCE",
            retention_until=retention_until or "2036-08-31T00:00:00Z",
            legal_hold=legal_hold,
            provider_receipt_ref="receipt-1",
            metadata=dict(metadata),
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        if self.readback_override is not None:
            return self.readback_override
        return self._stored[(object_ref, version_ref)]


def _identity() -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="actor-a",
        subject="subject-a",
        amr=("pwd", "webauthn"),
        session_ref="session-1",
        device_ref="device-1",
        request_ref="request-1",
    )


def test_secure_capture_preserves_original_receipt_identity_and_chronology():
    source = SourceAuthenticationReceipt(
        state="DKIM_VALID",
        scheme="DKIM",
        provider="mail-verifier",
        provider_ref="dkim-check-1",
        checked_at="2026-08-31T21:59:00+00:00",
    )
    captured = capture_original_evidence(
        original_store=FakeImmutableStore(),
        evidence_id="tenant-a:e1",
        identity=_identity(),
        source_type="email",
        source_ref="message-id:<abc@example.com>",
        content=b"From: customer@example.com\r\nSubject: change\r\n\r\nPlease use R17",
        content_type="message/rfc822",
        source_authentication=source,
        effective_at="2026-05-01T10:00:00+00:00",
        retention_until="2036-08-31T00:00:00Z",
        clock=lambda: datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc),
    )
    metadata = captured.evidence.metadata
    assert captured.delayed_evidence is True
    assert captured.strong_identity is True
    assert metadata["raw_content_persisted"] == "true"
    assert metadata["original_version_readback_verified"] is True
    assert metadata["immutability"] == "WORM_LOCKED"
    assert metadata["worm_lock_verified"] is True
    assert metadata["source_authentication"] == "DKIM_VALID"
    assert metadata["original_provider_receipt_ref"] == "receipt-1"
    assert metadata["first_seen_at"] == "2026-08-31T22:00:00+00:00"
    assert metadata["effective_at"] == "2026-05-01T10:00:00+00:00"
    assert len(metadata["content_sha512"]) == 128


def test_secure_capture_rejects_receipt_correct_but_wrong_version_readback():
    with pytest.raises(ValueError, match="readback does not match captured bytes"):
        capture_original_evidence(
            original_store=FakeImmutableStore(readback_override=b"different bytes"),
            evidence_id="tenant-a:e1",
            identity=_identity(),
            source_type="document",
            source_ref="change.pdf",
            content=b"actual evidence",
            content_type="application/pdf",
            source_authentication=SourceAuthenticationReceipt(state="UNVERIFIED", scheme="UPLOAD", provider="intake"),
            clock=lambda: datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc),
        )


def test_verified_source_authentication_requires_external_receipt_identity():
    with pytest.raises(ValueError, match="provider reference"):
        SourceAuthenticationReceipt(
            state="DKIM_VALID",
            scheme="DKIM",
            provider="mail-verifier",
        )


def test_verified_source_authentication_rejects_unzoned_checked_at():
    with pytest.raises(ValueError, match="timezone"):
        SourceAuthenticationReceipt(
            state="DKIM_VALID",
            scheme="DKIM",
            provider="mail-verifier",
            provider_ref="dkim-check-1",
            checked_at="2026-08-31T21:59:00",
        )


def test_secure_capture_rejects_unzoned_server_clock():
    source = SourceAuthenticationReceipt(state="UNVERIFIED", scheme="UPLOAD", provider="intake")
    with pytest.raises(ValueError, match="timezone-aware"):
        capture_original_evidence(
            original_store=FakeImmutableStore(),
            evidence_id="tenant-a:e2",
            identity=CaptureIdentity(tenant_id="tenant-a", actor_id="actor-a", subject="subject-a"),
            source_type="document",
            source_ref="change.pdf",
            content=b"evidence",
            content_type="application/pdf",
            source_authentication=source,
            clock=lambda: datetime(2026, 8, 31, 22, 0),
        )
