from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory_cloud.assurance_kernel import EvidenceEnvelope
from vertical_apps.industrial_claims.intake_authorization import (
    IntakeAuthorization,
    capture_authorized_original_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.secure_case_intake import (
    SecureCaseIntakeError,
    create_case_from_secure_capture,
)
from vertical_apps.industrial_claims.service import IndustrialClaimsService


NOW = datetime(2026, 9, 1, 18, 50, tzinfo=timezone.utc)


class Store:
    name = "fake-compliance-worm"

    def __init__(self, *, retention_mode="COMPLIANCE"):
        self.retention_mode = retention_mode
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
            retention_mode=self.retention_mode,
            retention_until=retention_until,
            legal_hold=False,
            provider_receipt_ref=f"receipt-{evidence_id}",
            metadata=dict(metadata),
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self._stored[(object_ref, version_ref)]


def _authorization(*, authorization_id="auth-001", case_ref="pilot-case-001"):
    return IntakeAuthorization(
        authorization_id=authorization_id,
        tenant_id="tenant-a",
        case_ref=case_ref,
        authorized_by_ref="customer-authorizer@example.test",
        authorized_at="2026-09-01T18:00:00+00:00",
        expires_at="2026-09-02T18:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T18:00:00+00:00",
        transfer_channel_ref="customer-specific-secure-channel-001",
        evidence_roles=("commercial_basis", "event", "cost"),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=1024 * 1024,
    )


def _identity():
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="operator-a",
        subject="operator-subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _capture_and_register(
    registry: SecureCaptureRegistry,
    *,
    role: str,
    evidence_id: str,
    source_ref: str,
    content: bytes,
    authorization=None,
    store=None,
):
    captured = capture_authorized_original_evidence(
        authorization=authorization or _authorization(),
        evidence_role=role,
        original_store=store or Store(),
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
    registry.record(
        evidence=captured.evidence,
        evidence_role=role,
        captured_by="operator-a",
    )
    return captured.evidence


def _registered_triplet(database, *, mixed_authorization=False, cost_store=None):
    registry = SecureCaptureRegistry(database)
    basis = _capture_and_register(
        registry,
        role="commercial_basis",
        evidence_id="tenant-a:pilot-case-001:basis",
        source_ref="po-1",
        content=b"signed purchase order terms",
    )
    event = _capture_and_register(
        registry,
        role="event",
        evidence_id="tenant-a:pilot-case-001:event",
        source_ref="change-17",
        content=b"customer directed engineering change",
        authorization=_authorization(authorization_id="auth-OTHER") if mixed_authorization else None,
    )
    cost = _capture_and_register(
        registry,
        role="cost",
        evidence_id="tenant-a:pilot-case-001:cost",
        source_ref="ledger-1",
        content=b"engineering time ledger",
        store=cost_store,
    )
    return registry, basis, event, cost


def _create(service, registry, *, evidence_ids=None, tenant_id="tenant-a"):
    return create_case_from_secure_capture(
        service,
        registry,
        tenant_id=tenant_id,
        actor_id="analyst-a",
        intake_case_ref="pilot-case-001",
        evidence_ids=evidence_ids or {
            "commercial_basis": "tenant-a:pilot-case-001:basis",
            "event": "tenant-a:pilot-case-001:event",
            "cost": "tenant-a:pilot-case-001:cost",
        },
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="change-17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="10000",
        currency="EUR",
        notice_deadline_not_applicable=True,
    )


def test_authorized_worm_originals_become_exact_case_lineage_without_reupload(tmp_path):
    database = tmp_path / "secure-case.sqlite3"
    registry, basis, event, cost = _registered_triplet(database)
    service = IndustrialClaimsService(database)

    result = _create(service, registry)
    assert result.finding.state == "READY_FOR_REVIEW"
    assert result.is_new_recovery is True
    assert result.finding.evidence_ids == (basis.evidence_id, event.evidence_id, cost.evidence_id)
    assert tuple(item.evidence_id for item in result.evidence) == result.finding.evidence_ids
    assert all(item.metadata["raw_content_persisted"] == "true" for item in result.evidence)
    assert all(item.metadata["original_version_readback_verified"] is True for item in result.evidence)
    assert all(item.metadata["immutability"] == "WORM_LOCKED" for item in result.evidence)
    assert all(item.metadata["intake_authorization_id"] == "auth-001" for item in result.evidence)
    assert all(item.metadata["source_authentication"] == "UNVERIFIED" for item in result.evidence)

    detail = service.read_model.get_finding(
        tenant_id="tenant-a",
        finding_id=result.finding.finding_id,
    )
    assert detail["raw_document_content_included"] is False
    assert {item["evidence_id"] for item in detail["evidence_index"]} == set(result.finding.evidence_ids)


def test_secure_case_creation_is_idempotent_for_same_exact_registered_originals(tmp_path):
    database = tmp_path / "secure-replay.sqlite3"
    registry, _basis, _event, _cost = _registered_triplet(database)
    service = IndustrialClaimsService(database)

    first = _create(service, registry)
    second = _create(service, registry)
    assert first.finding.finding_id == second.finding.finding_id
    assert first.is_new_recovery is True
    assert second.is_new_recovery is False
    assert service.store.count("findings", "tenant-a") == 1
    assert service.store.count("evidence", "tenant-a") == 3


def test_secure_case_refuses_cross_tenant_or_incomplete_role_set(tmp_path):
    database = tmp_path / "secure-scope.sqlite3"
    registry, _basis, _event, _cost = _registered_triplet(database)
    service = IndustrialClaimsService(database)

    with pytest.raises(Exception, match="not found|tenant"):
        _create(service, registry, tenant_id="tenant-b")

    with pytest.raises(SecureCaseIntakeError, match="exactly commercial_basis, event and cost"):
        _create(
            service,
            registry,
            evidence_ids={
                "commercial_basis": "tenant-a:pilot-case-001:basis",
                "event": "tenant-a:pilot-case-001:event",
            },
        )
    assert service.store.count("findings", "tenant-a") == 0


def test_secure_case_refuses_mixed_authorization_scopes_before_case_persistence(tmp_path):
    database = tmp_path / "mixed-auth.sqlite3"
    registry, _basis, _event, _cost = _registered_triplet(database, mixed_authorization=True)
    service = IndustrialClaimsService(database)

    with pytest.raises(SecureCaseIntakeError, match="one intake authorization scope"):
        _create(service, registry)
    assert service.store.count("findings", "tenant-a") == 0
    assert service.store.count("evidence", "tenant-a") == 0


def test_secure_case_refuses_non_worm_original_even_if_registry_record_exists(tmp_path):
    database = tmp_path / "non-worm.sqlite3"
    registry, _basis, _event, _cost = _registered_triplet(
        database,
        cost_store=Store(retention_mode="GOVERNANCE"),
    )
    service = IndustrialClaimsService(database)

    with pytest.raises(SecureCaseIntakeError, match="not WORM locked"):
        _create(service, registry)
    assert service.store.count("findings", "tenant-a") == 0


def test_secure_case_refuses_intake_case_substitution_even_with_valid_registered_evidence(tmp_path):
    database = tmp_path / "case-substitution.sqlite3"
    registry, _basis, _event, _cost = _registered_triplet(database)
    service = IndustrialClaimsService(database)

    with pytest.raises(SecureCaseIntakeError, match="does not belong to requested intake case"):
        create_case_from_secure_capture(
            service,
            registry,
            tenant_id="tenant-a",
            actor_id="analyst-a",
            intake_case_ref="different-case",
            evidence_ids={
                "commercial_basis": "tenant-a:pilot-case-001:basis",
                "event": "tenant-a:pilot-case-001:event",
                "cost": "tenant-a:pilot-case-001:cost",
            },
            customer_ref="oem-1",
            program_ref="program-1",
            event_ref="change-17",
            claim_family="NRE",
            commercial_basis_ref="po-1",
            cost_evidence_ref="ledger-1",
            gross_cost="10000",
            currency="EUR",
            notice_deadline_not_applicable=True,
        )
    assert service.store.count("findings", "tenant-a") == 0
