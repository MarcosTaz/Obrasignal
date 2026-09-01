from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from vertical_apps.industrial_claims.intake_authorization import (
    IntakeAuthorization,
    capture_authorized_original_evidence,
)
from vertical_apps.industrial_claims.outcome_authorization import (
    OutcomeEvidenceAuthorization,
    capture_authorized_outcome_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry, SecureCaptureRegistryError
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry, SecureOutcomeRegistryError


NOW = datetime(2026, 9, 1, 21, 30, tzinfo=timezone.utc)


class Store:
    name = "fake-compliance-worm"

    def __init__(self):
        self._stored: dict[tuple[str, str], bytes] = {}

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        object_ref = f"{tenant_id}/{evidence_id}"
        version_ref = "v1"
        self._stored[(object_ref, version_ref)] = content
        digests = dual_digest(content)
        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=object_ref,
            version_ref=version_ref,
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode="COMPLIANCE",
            retention_until=retention_until,
            legal_hold=False,
            provider_receipt_ref=f"receipt-{evidence_id}",
            metadata=dict(metadata),
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self._stored[(object_ref, version_ref)]


def _identity() -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="operator-a",
        subject="operator-subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _source_authentication() -> SourceAuthenticationReceipt:
    return SourceAuthenticationReceipt(
        state="UNVERIFIED",
        scheme="AUTHORIZED_UPLOAD",
        provider="pilot-intake",
    )


def test_secure_capture_registry_rejects_received_at_moved_outside_intake_authorization_window(tmp_path):
    database = tmp_path / "intake-window.sqlite3"
    store = Store()
    registry = SecureCaptureRegistry(database)
    captured = capture_authorized_original_evidence(
        authorization=IntakeAuthorization(
            authorization_id="auth-window-1",
            tenant_id="tenant-a",
            case_ref="case-window-1",
            authorized_by_ref="controller@example.test",
            authorized_at="2026-09-01T20:00:00+00:00",
            expires_at="2026-09-01T22:00:00+00:00",
            minimum_immutable_retention_until="2027-09-01T22:00:00+00:00",
            transfer_channel_ref="secure-channel",
            evidence_roles=("commercial_basis", "event", "cost"),
            data_terms_state="SIGNED",
            immutable_retention_acknowledged=True,
        ),
        evidence_role="commercial_basis",
        original_store=store,
        evidence_id="tenant-a:case-window-1:commercial_basis",
        identity=_identity(),
        source_ref="po-window",
        content=b"authorized commercial basis",
        content_type="application/pdf",
        source_authentication=_source_authentication(),
        clock=lambda: NOW,
    )
    registry.record(evidence=captured.evidence, evidence_role="commercial_basis", captured_by="operator-a")

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_secure_capture_no_update")
        conn.execute(
            "UPDATE causledger_secure_capture_envelopes SET received_at=? WHERE evidence_id=?",
            ("2026-09-01T23:00:00+00:00", captured.evidence.evidence_id),
        )
        conn.commit()

    with pytest.raises(SecureCaptureRegistryError, match="outside authorized intake window"):
        registry.get(tenant_id="tenant-a", evidence_id=captured.evidence.evidence_id)


def test_secure_outcome_registry_rejects_received_at_moved_outside_outcome_authorization_window(tmp_path):
    database = tmp_path / "outcome-window.sqlite3"
    store = Store()
    registry = SecureOutcomeRegistry(database)
    finding_id = "tenant-a:finding-window-1"
    captured = capture_authorized_outcome_evidence(
        authorization=OutcomeEvidenceAuthorization(
            authorization_id="outcome-window-1",
            tenant_id="tenant-a",
            finding_id=finding_id,
            authorized_by_ref="controller@example.test",
            authorized_at="2026-09-01T20:00:00+00:00",
            expires_at="2026-09-01T22:00:00+00:00",
            minimum_immutable_retention_until="2027-09-01T22:00:00+00:00",
            transfer_channel_ref="secure-outcome-channel",
            data_terms_state="SIGNED",
            immutable_retention_acknowledged=True,
        ),
        original_store=store,
        evidence_id="tenant-a:outcome-window-1:payment",
        identity=_identity(),
        source_ref="bank-window",
        content=b"authorized settlement evidence",
        content_type="application/pdf",
        source_authentication=_source_authentication(),
        clock=lambda: NOW,
    )
    registry.record(evidence=captured.evidence, captured_by="operator-a")

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_secure_outcome_no_update")
        conn.execute(
            "UPDATE causledger_secure_outcome_envelopes SET received_at=? WHERE evidence_id=?",
            ("2026-09-01T19:00:00+00:00", captured.evidence.evidence_id),
        )
        conn.commit()

    with pytest.raises(SecureOutcomeRegistryError, match="outside authorized outcome window"):
        registry.get(
            tenant_id="tenant-a",
            evidence_id=captured.evidence.evidence_id,
            finding_id=finding_id,
            source_ref="bank-window",
        )
