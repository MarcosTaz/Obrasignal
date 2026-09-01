from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.outcome_authorization import (
    OutcomeAuthorizationError,
    OutcomeEvidenceAuthorization,
    capture_authorized_outcome_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry, SecureOutcomeRegistryError
from vertical_apps.industrial_claims.secure_outcome_resolution import resolve_from_secure_outcome
from vertical_apps.industrial_claims.service import IndustrialClaimsService


NOW = datetime(2026, 9, 1, 20, 15, tzinfo=timezone.utc)


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


def _identity() -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="operator-a",
        subject="operator-subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _actioned_case(database):
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="change-17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="synthetic purchase order terms",
        event_evidence_content="synthetic customer change",
        cost_evidence_content="synthetic cost ledger",
        notice_deadline_not_applicable=True,
    )
    finding_id = result.finding.finding_id
    assert service.review(
        tenant_id="tenant-a",
        finding_id=finding_id,
        reviewer="reviewer-b",
        approved=True,
        reason="synthetic independent review",
    ) == "APPROVED"
    assert service.action(tenant_id="tenant-a", finding_id=finding_id, actor_id="operator-a") == "ACTIONED"
    return service, finding_id


def _authorization(finding_id: str, *, purpose="DOCUMENTED_FINAL_OUTCOME_RECORDING"):
    return OutcomeEvidenceAuthorization(
        authorization_id="outcome-auth-1",
        tenant_id="tenant-a",
        finding_id=finding_id,
        authorized_by_ref="customer-controller@example.test",
        authorized_at="2026-09-01T20:00:00+00:00",
        expires_at="2026-09-02T20:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T20:00:00+00:00",
        transfer_channel_ref="secure-outcome-channel-1",
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        purpose=purpose,
        max_bytes=1024 * 1024,
    )


def _capture(registry, finding_id, *, store=None, evidence_id="tenant-a:outcome:payment-1"):
    captured = capture_authorized_outcome_evidence(
        authorization=_authorization(finding_id),
        original_store=store or Store(),
        evidence_id=evidence_id,
        identity=_identity(),
        source_ref="bank-settlement-1",
        content=b"synthetic final settlement evidence",
        content_type="application/pdf",
        source_authentication=SourceAuthenticationReceipt(
            state="UNVERIFIED",
            scheme="AUTHORIZED_UPLOAD",
            provider="pilot-outcome-intake",
        ),
        clock=lambda: NOW,
    )
    registry.record(evidence=captured.evidence, captured_by="operator-a")
    return captured.evidence


def test_secure_outcome_closes_actioned_finding_with_exact_registered_evidence(tmp_path):
    database = tmp_path / "secure-outcome.sqlite3"
    service, finding_id = _actioned_case(database)
    registry = SecureOutcomeRegistry(database)
    evidence = _capture(registry, finding_id)

    outcome = resolve_from_secure_outcome(
        service,
        registry,
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="payment-1",
        recovered_amount="7500",
        currency="EUR",
        evidence_id=evidence.evidence_id,
        evidence_ref="bank-settlement-1",
        actor_id="operator-c",
        final_cumulative=True,
    )

    assert outcome.finding_id == finding_id
    assert outcome.evidence_ref == evidence.evidence_id
    detail = service.read_model.get_finding(tenant_id="tenant-a", finding_id=finding_id)
    assert detail["finding"]["state"] == "RECOVERED"
    assert len(detail["outcomes"]) == 1
    assert detail["outcomes"][0]["evidence"]["evidence_id"] == evidence.evidence_id
    assert detail["outcomes"][0]["evidence"]["verification_state"] == "CONTENT_HASHED"
    assert service.store.count("evidence", "tenant-a") == 4


def test_secure_outcome_rejects_amount_above_reviewed_maximum_before_outcome_mutation(tmp_path):
    database = tmp_path / "secure-outcome-cap.sqlite3"
    service, finding_id = _actioned_case(database)
    registry = SecureOutcomeRegistry(database)
    evidence = _capture(registry, finding_id)

    with pytest.raises(AssuranceOperationError, match="exceeds reviewed net potential"):
        resolve_from_secure_outcome(
            service,
            registry,
            tenant_id="tenant-a",
            finding_id=finding_id,
            outcome_id="payment-1",
            recovered_amount="10001",
            currency="EUR",
            evidence_id=evidence.evidence_id,
            evidence_ref="bank-settlement-1",
            actor_id="operator-c",
            final_cumulative=True,
        )
    detail = service.read_model.get_finding(tenant_id="tenant-a", finding_id=finding_id)
    assert detail["finding"]["state"] == "ACTIONED"
    assert detail["outcomes"] == []


def test_secure_outcome_cannot_be_rebound_to_a_different_finding(tmp_path):
    database = tmp_path / "secure-outcome-binding.sqlite3"
    service, finding_id = _actioned_case(database)
    registry = SecureOutcomeRegistry(database)
    evidence = _capture(registry, finding_id)

    other = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-2",
        program_ref="program-2",
        event_ref="change-22",
        claim_family="NRE",
        commercial_basis_ref="po-2",
        cost_evidence_ref="ledger-2",
        gross_cost="1000",
        currency="EUR",
        commercial_basis_content="synthetic po 2",
        event_evidence_content="synthetic event 2",
        cost_evidence_content="synthetic ledger 2",
        notice_deadline_not_applicable=True,
    )
    other_id = other.finding.finding_id
    service.review(tenant_id="tenant-a", finding_id=other_id, reviewer="reviewer-b", approved=True, reason="synthetic review")
    service.action(tenant_id="tenant-a", finding_id=other_id, actor_id="operator-a")

    with pytest.raises(SecureOutcomeRegistryError, match="finding binding"):
        resolve_from_secure_outcome(
            service,
            registry,
            tenant_id="tenant-a",
            finding_id=other_id,
            outcome_id="payment-1",
            recovered_amount="500",
            currency="EUR",
            evidence_id=evidence.evidence_id,
            evidence_ref="bank-settlement-1",
            actor_id="operator-c",
            final_cumulative=True,
        )


def test_secure_outcome_registry_rejects_non_compliance_retention(tmp_path):
    database = tmp_path / "secure-outcome-worm.sqlite3"
    _service, finding_id = _actioned_case(database)
    registry = SecureOutcomeRegistry(database)
    captured = capture_authorized_outcome_evidence(
        authorization=_authorization(finding_id),
        original_store=Store(retention_mode="GOVERNANCE"),
        evidence_id="tenant-a:outcome:payment-1",
        identity=_identity(),
        source_ref="bank-settlement-1",
        content=b"synthetic final settlement evidence",
        content_type="application/pdf",
        source_authentication=SourceAuthenticationReceipt(
            state="UNVERIFIED",
            scheme="AUTHORIZED_UPLOAD",
            provider="pilot-outcome-intake",
        ),
        clock=lambda: NOW,
    )
    with pytest.raises(SecureOutcomeRegistryError, match="not WORM locked"):
        registry.record(evidence=captured.evidence, captured_by="operator-a")


def test_outcome_authorization_refuses_reusing_an_unrelated_purpose(tmp_path):
    database = tmp_path / "secure-outcome-purpose.sqlite3"
    _service, finding_id = _actioned_case(database)
    with pytest.raises(OutcomeAuthorizationError, match="purpose"):
        capture_authorized_outcome_evidence(
            authorization=_authorization(finding_id, purpose="BOUNDED_HISTORICAL_RAPID_SCAN"),
            original_store=Store(),
            evidence_id="tenant-a:outcome:payment-1",
            identity=_identity(),
            source_ref="bank-settlement-1",
            content=b"synthetic final settlement evidence",
            content_type="application/pdf",
            source_authentication=SourceAuthenticationReceipt(
                state="UNVERIFIED",
                scheme="AUTHORIZED_UPLOAD",
                provider="pilot-outcome-intake",
            ),
            clock=lambda: NOW,
        )


def test_outcome_capture_refuses_caller_override_of_content_hash_state(tmp_path):
    database = tmp_path / "secure-outcome-verification-state.sqlite3"
    _service, finding_id = _actioned_case(database)
    with pytest.raises(OutcomeAuthorizationError, match="verification state"):
        capture_authorized_outcome_evidence(
            authorization=_authorization(finding_id),
            original_store=Store(),
            evidence_id="tenant-a:outcome:payment-1",
            identity=_identity(),
            source_ref="bank-settlement-1",
            content=b"synthetic final settlement evidence",
            content_type="application/pdf",
            source_authentication=SourceAuthenticationReceipt(
                state="UNVERIFIED",
                scheme="AUTHORIZED_UPLOAD",
                provider="pilot-outcome-intake",
            ),
            metadata={"verification_state": "SOURCE_VERIFIED"},
            clock=lambda: NOW,
        )
