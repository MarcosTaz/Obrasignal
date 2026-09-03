from __future__ import annotations

from datetime import datetime, timezone

from vertical_apps.industrial_claims.intake_authorization import (
    IntakeAuthorization,
    capture_authorized_original_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry


NOW = datetime(2026, 9, 1, 18, 45, tzinfo=timezone.utc)
CONTENT = b"authorized historical commercial basis"


class ImmutableStore:
    name = "integration-worm"

    def __init__(self):
        self.payload = b""

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        self.payload = content
        digests = dual_digest(content)
        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=f"{tenant_id}/{evidence_id}",
            version_ref="v1",
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode="COMPLIANCE",
            retention_until=retention_until,
            legal_hold=False,
            provider_receipt_ref="receipt-integration-1",
            metadata={},
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self.payload


def test_bounded_authorization_capture_and_registry_form_one_fail_closed_chain(tmp_path):
    authorization = IntakeAuthorization(
        authorization_id="auth-integration-1",
        tenant_id="tenant-a",
        case_ref="case-integration-1",
        authorized_by_ref="authorized-customer-contact",
        authorized_at="2026-09-01T18:00:00+00:00",
        expires_at="2026-09-02T18:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T18:00:00+00:00",
        transfer_channel_ref="private-channel-1",
        evidence_roles=("commercial_basis",),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=10_000,
    )
    captured = capture_authorized_original_evidence(
        authorization=authorization,
        evidence_role="commercial_basis",
        original_store=ImmutableStore(),
        evidence_id="tenant-a:case-integration-1:commercial-basis",
        identity=CaptureIdentity(
            tenant_id="tenant-a",
            actor_id="operator-a",
            subject="subject-a",
            amr=("webauthn",),
        ),
        source_ref="po-excerpt.pdf",
        content=CONTENT,
        content_type="application/pdf",
        source_authentication=SourceAuthenticationReceipt(
            state="UNVERIFIED",
            scheme="AUTHORIZED_UPLOAD",
            provider="pilot-intake",
        ),
        clock=lambda: NOW,
    )

    registry = SecureCaptureRegistry(tmp_path / "authorized-capture.sqlite3")
    registered = registry.record(
        evidence=captured.evidence,
        evidence_role="commercial_basis",
        captured_by="operator-a",
    )
    loaded = registry.get(
        tenant_id="tenant-a",
        evidence_id=registered.evidence_id,
        evidence_role="commercial_basis",
        source_ref="po-excerpt.pdf",
    )

    assert loaded == captured.evidence
    assert loaded.metadata["intake_authorization_id"] == "auth-integration-1"
    assert loaded.metadata["intake_case_ref"] == "case-integration-1"
    assert loaded.metadata["original_retention_until"] == "2027-09-02T18:00:00+00:00"
    assert registry.count(tenant_id="tenant-a") == 1
