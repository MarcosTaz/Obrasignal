from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.intake_authorization import IntakeAuthorization, capture_authorized_original_evidence
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.secure_case_amendment import amend_case_from_secure_capture
from vertical_apps.industrial_claims.secure_case_intake import SecureCaseIntakeError, create_case_from_secure_capture
from vertical_apps.industrial_claims.service import IndustrialClaimsService


NOW = datetime(2026, 9, 1, 19, 30, tzinfo=timezone.utc)


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


def _authorization(authorization_id: str) -> IntakeAuthorization:
    return IntakeAuthorization(
        authorization_id=authorization_id,
        tenant_id="tenant-a",
        case_ref="pilot-case-001",
        authorized_by_ref="customer-authorizer@example.test",
        authorized_at="2026-09-01T18:00:00+00:00",
        expires_at="2026-09-02T18:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T18:00:00+00:00",
        transfer_channel_ref=f"secure-channel-{authorization_id}",
        evidence_roles=("commercial_basis", "event", "cost"),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=1024 * 1024,
    )


def _identity() -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="operator-a",
        subject="operator-subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _register_triplet(registry: SecureCaptureRegistry, *, suffix: str, authorization_id: str, mixed_event_auth: str | None = None):
    store = Store()
    definitions = {
        "commercial_basis": ("po-1", b"signed purchase order terms"),
        "event": ("change-17", b"customer directed engineering change"),
        "cost": (f"ledger-{suffix}", f"engineering time ledger {suffix}".encode()),
    }
    ids: dict[str, str] = {}
    envelopes = []
    for role, (source_ref, content) in definitions.items():
        evidence_id = f"tenant-a:pilot-case-001:{suffix}:{role}"
        selected_auth = mixed_event_auth if role == "event" and mixed_event_auth else authorization_id
        captured = capture_authorized_original_evidence(
            authorization=_authorization(selected_auth),
            evidence_role=role,
            original_store=store,
            evidence_id=evidence_id,
            identity=_identity(),
            source_ref=source_ref,
            content=content,
            content_type="application/pdf",
            source_authentication=SourceAuthenticationReceipt(
                state="UNVERIFIED",
                scheme="AUTHORIZED_UPLOAD",
                provider="pilot-intake",
            ),
            clock=lambda: NOW,
        )
        registry.record(evidence=captured.evidence, evidence_role=role, captured_by="operator-a")
        ids[role] = evidence_id
        envelopes.append(captured.evidence)
    return ids, tuple(envelopes)


def _create_initial(service: IndustrialClaimsService, registry: SecureCaptureRegistry, ids: dict[str, str]):
    return create_case_from_secure_capture(
        service,
        registry,
        tenant_id="tenant-a",
        actor_id="analyst-a",
        intake_case_ref="pilot-case-001",
        evidence_ids=ids,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="change-17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-r1",
        gross_cost="10000",
        currency="EUR",
        notice_deadline_not_applicable=True,
    )


def _amend(service: IndustrialClaimsService, registry: SecureCaptureRegistry, finding_id: str, ids: dict[str, str], **overrides):
    payload = {
        "tenant_id": "tenant-a",
        "finding_id": finding_id,
        "actor_id": "analyst-b",
        "intake_case_ref": "pilot-case-001",
        "evidence_ids": ids,
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "change-17",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-1",
        "cost_evidence_ref": "ledger-r2",
        "gross_cost": "12000",
        "currency": "EUR",
        "notice_deadline_not_applicable": True,
    }
    payload.update(overrides)
    return amend_case_from_secure_capture(service, registry, **payload)


def test_secure_amendment_supersedes_with_exact_new_originals_and_requires_fresh_review(tmp_path):
    database = tmp_path / "secure-amend.sqlite3"
    registry = SecureCaptureRegistry(database)
    first_ids, _ = _register_triplet(registry, suffix="r1", authorization_id="auth-r1")
    service = IndustrialClaimsService(database)
    original = _create_initial(service, registry, first_ids)

    second_ids, second_envelopes = _register_triplet(registry, suffix="r2", authorization_id="auth-r2")
    amended = _amend(service, registry, original.finding.finding_id, second_ids)

    assert amended.finding.finding_id != original.finding.finding_id
    assert amended.finding.state == "READY_FOR_REVIEW"
    assert amended.finding.reviewer is None
    assert set(amended.finding.evidence_ids) == set(second_ids.values())
    assert {item.evidence_id for item in amended.evidence} == {item.evidence_id for item in second_envelopes}
    assert all(item.metadata["intake_authorization_id"] == "auth-r2" for item in amended.evidence)
    assert service.store.count("findings", "tenant-a") == 2
    assert service.store.count("evidence", "tenant-a") == 6

    old_detail = service.read_model.get_finding(tenant_id="tenant-a", finding_id=original.finding.finding_id)
    new_detail = service.read_model.get_finding(tenant_id="tenant-a", finding_id=amended.finding.finding_id)
    assert old_detail["revision"]["is_current"] is False
    assert old_detail["revision"]["superseded_by_finding_id"] == amended.finding.finding_id
    assert new_detail["revision"]["revision"] == 2
    assert new_detail["revision"]["is_current"] is True
    assert new_detail["raw_document_content_included"] is False


def test_secure_amendment_rejects_fingerprint_identity_change_before_successor_persistence(tmp_path):
    database = tmp_path / "secure-amend-fingerprint.sqlite3"
    registry = SecureCaptureRegistry(database)
    first_ids, _ = _register_triplet(registry, suffix="r1", authorization_id="auth-r1")
    service = IndustrialClaimsService(database)
    original = _create_initial(service, registry, first_ids)
    second_ids, _ = _register_triplet(registry, suffix="r2", authorization_id="auth-r2")

    with pytest.raises(AssuranceOperationError, match="cannot change recovery fingerprint"):
        _amend(service, registry, original.finding.finding_id, second_ids, event_ref="different-change")

    assert service.store.count("findings", "tenant-a") == 1
    current = service.revision_store.require_current(
        tenant_id="tenant-a",
        finding_id=original.finding.finding_id,
    )
    assert current.revision == 1


def test_secure_amendment_rejects_mixed_authorization_scope_before_successor_persistence(tmp_path):
    database = tmp_path / "secure-amend-mixed.sqlite3"
    registry = SecureCaptureRegistry(database)
    first_ids, _ = _register_triplet(registry, suffix="r1", authorization_id="auth-r1")
    service = IndustrialClaimsService(database)
    original = _create_initial(service, registry, first_ids)
    second_ids, _ = _register_triplet(
        registry,
        suffix="r2",
        authorization_id="auth-r2",
        mixed_event_auth="auth-other",
    )

    with pytest.raises(SecureCaseIntakeError, match="one intake authorization scope"):
        _amend(service, registry, original.finding.finding_id, second_ids)

    assert service.store.count("findings", "tenant-a") == 1
