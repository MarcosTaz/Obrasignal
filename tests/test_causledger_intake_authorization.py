from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from vertical_apps.industrial_claims.intake_authorization import (
    IntakeAuthorization,
    IntakeAuthorizationError,
    capture_authorized_original_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt


NOW = datetime(2026, 9, 1, 18, 45, tzinfo=timezone.utc)
CONTENT = b"bounded historical customer change evidence"


class Store:
    name = "fake-worm"

    def __init__(self):
        self.payload = None
        self.retention_until = None
        self.metadata = None

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        self.payload = content
        self.retention_until = retention_until
        self.metadata = dict(metadata)
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
            provider_receipt_ref="receipt-1",
            metadata={},
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self.payload


def _authorization(**overrides):
    values = {
        "authorization_id": "auth-001",
        "tenant_id": "tenant-a",
        "case_ref": "pilot-case-001",
        "authorized_by_ref": "customer-authorizer@example.test",
        "authorized_at": "2026-09-01T18:00:00+00:00",
        "expires_at": "2026-09-02T18:00:00+00:00",
        "minimum_immutable_retention_until": "2027-09-02T18:00:00+00:00",
        "transfer_channel_ref": "customer-specific-secure-channel-001",
        "evidence_roles": ("commercial_basis", "event", "cost"),
        "data_terms_state": "SIGNED",
        "immutable_retention_acknowledged": True,
        "max_bytes_per_evidence": 1024,
    }
    values.update(overrides)
    return IntakeAuthorization(**values)


def _identity(tenant="tenant-a"):
    return CaptureIdentity(
        tenant_id=tenant,
        actor_id="operator-a",
        subject="subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _source():
    return SourceAuthenticationReceipt(state="UNVERIFIED", scheme="AUTHORIZED_UPLOAD", provider="pilot-intake")


def _capture(*, authorization=None, evidence_role="event", identity=None, content=CONTENT, metadata=None):
    store = Store()
    captured = capture_authorized_original_evidence(
        authorization=authorization or _authorization(),
        evidence_role=evidence_role,
        original_store=store,
        evidence_id="tenant-a:pilot-case-001:event-1",
        identity=identity or _identity(),
        source_ref="customer-change.pdf",
        content=content,
        content_type="application/pdf",
        source_authentication=_source(),
        metadata=metadata,
        clock=lambda: NOW,
    )
    return captured, store


def test_authorized_capture_binds_scope_without_persisting_raw_authorizer_or_channel_reference():
    captured, store = _capture()
    metadata = captured.evidence.metadata
    assert metadata["intake_authorization_id"] == "auth-001"
    assert metadata["intake_case_ref"] == "pilot-case-001"
    assert metadata["intake_purpose"] == "BOUNDED_HISTORICAL_RAPID_SCAN"
    assert metadata["intake_evidence_role"] == "event"
    assert metadata["intake_data_terms_state"] == "SIGNED"
    assert metadata["intake_immutable_retention_acknowledged"] is True
    assert len(metadata["intake_authorization_scope_sha256"]) == 64
    assert len(metadata["intake_authorized_by_sha256"]) == 64
    assert len(metadata["intake_transfer_channel_sha256"]) == 64
    assert "customer-authorizer@example.test" not in str(metadata)
    assert "customer-specific-secure-channel-001" not in str(metadata)
    assert store.retention_until == "2027-09-02T18:00:00+00:00"
    assert store.metadata["intake_authorization_scope_sha256"] == metadata["intake_authorization_scope_sha256"]


@pytest.mark.parametrize(
    "authorization,error",
    [
        (_authorization(authorized_at="2026-09-01T19:00:00+00:00"), "not yet effective"),
        (_authorization(expires_at="2026-09-01T18:30:00+00:00"), "expired"),
        (_authorization(data_terms_state="PENDING"), "data terms are not cleared"),
        (_authorization(immutable_retention_acknowledged=False), "must be explicitly acknowledged"),
        (_authorization(minimum_immutable_retention_until="2026-09-01T18:30:00+00:00"), "retention is already expired"),
    ],
)
def test_authorization_must_be_current_cleared_and_retention_acknowledged(authorization, error):
    with pytest.raises(IntakeAuthorizationError, match=error):
        _capture(authorization=authorization)


def test_authorized_capture_rejects_cross_tenant_cross_role_and_oversized_content():
    with pytest.raises(IntakeAuthorizationError, match="tenant does not match"):
        _capture(identity=_identity("tenant-b"))
    with pytest.raises(IntakeAuthorizationError, match="outside authorized intake scope"):
        _capture(authorization=_authorization(evidence_roles=("commercial_basis",)), evidence_role="event")
    with pytest.raises(IntakeAuthorizationError, match="byte limit"):
        _capture(authorization=_authorization(max_bytes_per_evidence=4), content=CONTENT)


def test_authorized_capture_rejects_caller_attempt_to_spoof_authorization_metadata():
    with pytest.raises(IntakeAuthorizationError, match="cannot override"):
        _capture(metadata={"intake_authorization_id": "forged"})


def test_authorization_scope_hash_changes_when_material_scope_changes():
    base = _authorization().validated(now=NOW)
    changed = replace(_authorization(), case_ref="pilot-case-002").validated(now=NOW)
    assert base.scope_sha256 != changed.scope_sha256


def test_authorization_rejects_unapproved_purpose_and_invalid_role_set():
    with pytest.raises(IntakeAuthorizationError, match="purpose"):
        _authorization(purpose="BULK_MAILBOX_DISCOVERY").validated(now=NOW)
    with pytest.raises(IntakeAuthorizationError, match="roles"):
        _authorization(evidence_roles=("full_mailbox",)).validated(now=NOW)
