from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from factory_cloud.assurance_kernel import EvidenceEnvelope
from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.outcome_authorization import (
    OutcomeEvidenceAuthorization,
    capture_authorized_outcome_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry
from vertical_apps.industrial_claims.secure_outcome_resolution import resolve_from_secure_outcome
from vertical_apps.industrial_claims.service import IndustrialClaimsService


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


def _actioned_case(database) -> tuple[IndustrialClaimsService, str]:
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="change-a",
        claim_family="NRE",
        commercial_basis_ref="po-a",
        cost_evidence_ref="ledger-a",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="synthetic signed commercial basis",
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
        reason="synthetic independent documentary review",
    ) == "APPROVED"
    assert service.action(
        tenant_id="tenant-a",
        finding_id=finding_id,
        actor_id="operator-c",
    ) == "ACTIONED"
    return service, finding_id


def _secure_identity() -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="operator-c",
        subject="operator-subject-c",
        amr=("webauthn",),
        session_ref="session-c",
        request_ref="request-c",
    )


def _secure_authorization(finding_id: str) -> OutcomeEvidenceAuthorization:
    return OutcomeEvidenceAuthorization(
        authorization_id="outcome-auth-lineage",
        tenant_id="tenant-a",
        finding_id=finding_id,
        authorized_by_ref="customer-controller@example.test",
        authorized_at="2026-09-01T20:00:00+00:00",
        expires_at="2026-09-02T20:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T20:00:00+00:00",
        transfer_channel_ref="secure-outcome-channel",
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes=1024 * 1024,
    )


def test_durable_proof_rejects_outcome_reference_substitution_even_to_same_tenant_valid_evidence(tmp_path):
    database = tmp_path / "outcome-reference-substitution.sqlite3"
    service, finding_id = _actioned_case(database)
    outcome = service.resolve(
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="payment-1",
        recovered_amount="7500",
        currency="EUR",
        evidence_ref="bank-proof-original",
        evidence_content="synthetic original final bank proof",
        actor_id="operator-d",
    )
    build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    alternate = EvidenceEnvelope.create(
        evidence_id="tenant-a:alternate-outcome-evidence",
        tenant_id="tenant-a",
        source_type="recovery_outcome_evidence",
        source_ref="bank-proof-alternate",
        content=b"synthetic alternate same-tenant outcome evidence",
        metadata={"verification_state": "CONTENT_HASHED", "raw_content_persisted": False},
    )
    service.store.put_evidence(alternate)
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE recovery_outcomes SET evidence_ref=? WHERE tenant_id=? AND outcome_id=?",
            (alternate.evidence_id, "tenant-a", outcome.outcome_id),
        )
        conn.commit()

    with pytest.raises(AssuranceStoreError, match="resolution audit evidence binding mismatch"):
        build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)


def test_durable_proof_rejects_resolution_audit_payload_rewrite(tmp_path):
    database = tmp_path / "outcome-audit-tamper.sqlite3"
    service, finding_id = _actioned_case(database)
    outcome = service.resolve(
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="payment-1",
        recovered_amount="7500",
        currency="EUR",
        evidence_ref="bank-proof-original",
        evidence_content="synthetic original final bank proof",
        actor_id="operator-d",
    )
    build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    event_id = f"tenant-a:{outcome.outcome_id}:resolve"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE audit_events SET payload_hash=? WHERE tenant_id=? AND event_id=?",
            ("0" * 64, "tenant-a", event_id),
        )
        conn.commit()

    with pytest.raises(AssuranceStoreError, match="resolution audit payload binding mismatch"):
        build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)


def test_durable_proof_rejects_secure_outcome_metadata_drift_from_authorized_registry(tmp_path):
    database = tmp_path / "secure-outcome-registry-drift.sqlite3"
    service, finding_id = _actioned_case(database)
    store = Store()
    registry = SecureOutcomeRegistry(database)
    evidence_id = "tenant-a:secure-outcome:payment-1"
    captured = capture_authorized_outcome_evidence(
        authorization=_secure_authorization(finding_id),
        original_store=store,
        evidence_id=evidence_id,
        identity=_secure_identity(),
        source_ref="bank-proof-secure",
        content=b"secure final settlement proof",
        content_type="application/pdf",
        source_authentication=SourceAuthenticationReceipt(
            state="UNVERIFIED",
            scheme="AUTHORIZED_UPLOAD",
            provider="pilot-outcome-intake",
        ),
        clock=lambda: NOW,
    )
    registry.record(evidence=captured.evidence, captured_by="operator-c")
    resolve_from_secure_outcome(
        service,
        registry,
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="payment-1",
        recovered_amount="7500",
        currency="EUR",
        evidence_id=evidence_id,
        evidence_ref="bank-proof-secure",
        actor_id="operator-d",
        final_cumulative=True,
    )
    pack = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
    assert pack["core_package"]["truth_boundaries"]["secure_outcome_bound_to_authorization_registry"] is True

    with sqlite3.connect(database) as conn:
        row = conn.execute(
            "SELECT metadata_json FROM evidence WHERE tenant_id=? AND evidence_id=?",
            ("tenant-a", evidence_id),
        ).fetchone()
        metadata = json.loads(row[0])
        metadata["outcome_finding_id"] = "tenant-a:some-other-finding"
        conn.execute(
            "UPDATE evidence SET metadata_json=? WHERE tenant_id=? AND evidence_id=?",
            (json.dumps(metadata, sort_keys=True, separators=(",", ":")), "tenant-a", evidence_id),
        )
        conn.commit()

    with pytest.raises(AssuranceStoreError, match="secure outcome finding authorization mismatch"):
        build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
