from __future__ import annotations

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

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        digests = dual_digest(content)
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


def test_secure_capture_preserves_original_receipt_identity_and_chronology():
    identity = CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="actor-a",
        subject="subject-a",
        amr=("pwd", "webauthn"),
        session_ref="session-1",
        device_ref="device-1",
        request_ref="request-1",
    )
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
        identity=identity,
        source_type="email",
        source_ref="message-id:<abc@example.com>",
        content=b"From: customer@example.com\r\nSubject: change\r\n\r\nPlease use R17",
        content_type="message/rfc822",
        source_authentication=source,
        effective_at="2026-05-01T10:00:00+00:00",
        first_seen_at="2026-08-31T22:00:00+00:00",
        retention_until="2036-08-31T00:00:00Z",
    )
    metadata = captured.evidence.metadata
    assert captured.delayed_evidence is True
    assert captured.strong_identity is True
    assert metadata["raw_content_persisted"] == "true"
    assert metadata["immutability"] == "WORM_LOCKED"
    assert metadata["source_authentication"] == "DKIM_VALID"
    assert metadata["original_provider_receipt_ref"] == "receipt-1"
    assert metadata["first_seen_at"] == "2026-08-31T22:00:00+00:00"
    assert metadata["effective_at"] == "2026-05-01T10:00:00+00:00"
    assert len(metadata["content_sha512"]) == 128


def test_verified_source_authentication_requires_external_receipt_identity():
    with pytest.raises(ValueError, match="provider reference"):
        SourceAuthenticationReceipt(
            state="DKIM_VALID",
            scheme="DKIM",
            provider="mail-verifier",
        )
