from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.intake_authorization import (
    IntakeAuthorization,
    capture_authorized_original_evidence,
)
from vertical_apps.industrial_claims.offline_export_bundle import (
    build_durable_offline_verification_export_bundle,
)
from vertical_apps.industrial_claims.outcome_authorization import (
    OutcomeEvidenceAuthorization,
    capture_authorized_outcome_evidence,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import (
    CaptureIdentity,
    SourceAuthenticationReceipt,
)
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.secure_case_intake import create_case_from_secure_capture
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry
from vertical_apps.industrial_claims.secure_outcome_resolution import resolve_from_secure_outcome
from vertical_apps.industrial_claims.service import IndustrialClaimsService


NOW = datetime(2026, 9, 1, 20, 30, tzinfo=timezone.utc)
OUTCOME_BYTES = b"SECRET FINAL SETTLEMENT PAYMENT EVIDENCE"


class Store:
    name = "fake-compliance-worm"

    def __init__(self):
        self._stored: dict[tuple[str, str], bytes] = {}
        self.reads: list[tuple[str, str, str, str]] = []

    def put_immutable(
        self,
        *,
        tenant_id,
        evidence_id,
        content,
        content_type,
        retention_until,
        legal_hold,
        metadata,
    ):
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
        self.reads.append((tenant_id, evidence_id, object_ref, version_ref))
        return self._stored[(object_ref, version_ref)]


def _identity(actor_id: str) -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id=actor_id,
        subject=f"subject-{actor_id}",
        amr=("webauthn",),
        session_ref=f"session-{actor_id}",
        request_ref=f"request-{actor_id}",
    )


def _intake_authorization() -> IntakeAuthorization:
    return IntakeAuthorization(
        authorization_id="case-auth-1",
        tenant_id="tenant-a",
        case_ref="historical-case-1",
        authorized_by_ref="customer-controller@example.test",
        authorized_at="2026-09-01T18:00:00+00:00",
        expires_at="2026-09-02T18:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T18:00:00+00:00",
        transfer_channel_ref="secure-case-channel-1",
        evidence_roles=("commercial_basis", "event", "cost"),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=1024 * 1024,
    )


def _seed_secure_actioned_case(database, store: Store):
    service = IndustrialClaimsService(database)
    registry = SecureCaptureRegistry(database)
    originals = {
        "commercial_basis": b"SECRET SIGNED PURCHASE ORDER BASIS",
        "event": b"SECRET CUSTOMER DIRECTED ENGINEERING CHANGE",
        "cost": b"SECRET INCREMENTAL ENGINEERING COST LEDGER",
    }
    refs = {
        "commercial_basis": "po-1",
        "event": "change-17",
        "cost": "ledger-1",
    }
    ids: dict[str, str] = {}
    for role in ("commercial_basis", "event", "cost"):
        evidence_id = f"tenant-a:historical-case-1:{role}"
        captured = capture_authorized_original_evidence(
            authorization=_intake_authorization(),
            evidence_role=role,
            original_store=store,
            evidence_id=evidence_id,
            identity=_identity("operator-a"),
            source_ref=refs[role],
            content=originals[role],
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
        ids[role] = evidence_id

    result = create_case_from_secure_capture(
        service,
        registry,
        tenant_id="tenant-a",
        actor_id="analyst-a",
        intake_case_ref="historical-case-1",
        evidence_ids=ids,
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref=refs["event"],
        claim_family="NRE",
        commercial_basis_ref=refs["commercial_basis"],
        cost_evidence_ref=refs["cost"],
        gross_cost="10000",
        currency="EUR",
        notice_deadline_not_applicable=True,
    )
    finding_id = result.finding.finding_id
    assert service.review(
        tenant_id="tenant-a",
        finding_id=finding_id,
        reviewer="reviewer-b",
        approved=True,
        reason="documentary candidate independently reviewed",
    ) == "APPROVED"
    assert service.action(
        tenant_id="tenant-a",
        finding_id=finding_id,
        actor_id="operator-c",
    ) == "ACTIONED"
    return service, finding_id, ids, originals


def _outcome_authorization(finding_id: str) -> OutcomeEvidenceAuthorization:
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
        max_bytes=1024 * 1024,
    )


def _resolve_secure_outcome(service, database, store: Store, finding_id: str) -> str:
    registry = SecureOutcomeRegistry(database)
    evidence_id = "tenant-a:outcome:payment-1"
    captured = capture_authorized_outcome_evidence(
        authorization=_outcome_authorization(finding_id),
        original_store=store,
        evidence_id=evidence_id,
        identity=_identity("operator-c"),
        source_ref="bank-settlement-1",
        content=OUTCOME_BYTES,
        content_type="application/pdf",
        source_authentication=SourceAuthenticationReceipt(
            state="UNVERIFIED",
            scheme="AUTHORIZED_UPLOAD",
            provider="pilot-outcome-intake",
        ),
        clock=lambda: NOW,
    )
    registry.record(evidence=captured.evidence, captured_by="operator-c")
    outcome = resolve_from_secure_outcome(
        service,
        registry,
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="payment-1",
        recovered_amount="7500",
        currency="EUR",
        evidence_id=evidence_id,
        evidence_ref="bank-settlement-1",
        actor_id="operator-d",
        final_cumulative=True,
    )
    assert outcome.evidence_ref == evidence_id
    return evidence_id


def test_recovered_proof_manifest_and_offline_export_include_exact_final_outcome_original(tmp_path):
    database = tmp_path / "recovered-offline.sqlite3"
    store = Store()
    service, finding_id, initial_ids, initial_originals = _seed_secure_actioned_case(database, store)
    outcome_evidence_id = _resolve_secure_outcome(service, database, store, finding_id)

    pack = build_durable_claim_proof_pack(
        service,
        tenant_id="tenant-a",
        finding_id=finding_id,
    )
    assert pack["core_package"]["finding"]["state"] == "RECOVERED"
    assert pack["core_package"]["truth_boundaries"]["final_outcome_evidence_in_manifest_when_present"] is True

    manifest_evidence = {
        item["evidence_id"]: item
        for item in pack["proof_manifest"]["evidence"]
    }
    expected_ids = set(initial_ids.values()) | {outcome_evidence_id}
    assert set(manifest_evidence) == expected_ids
    assert len(manifest_evidence) == 4
    outcome_manifest = manifest_evidence[outcome_evidence_id]
    assert outcome_manifest["source_type"] == "recovery_outcome_evidence"
    assert outcome_manifest["hashes"]["sha256"] == hashlib.sha256(OUTCOME_BYTES).hexdigest()
    assert outcome_manifest["hashes"]["sha512"] == hashlib.sha512(OUTCOME_BYTES).hexdigest()
    assert outcome_manifest["byte_length"] == len(OUTCOME_BYTES)
    assert outcome_manifest["raw_content_persisted"] is True

    bundle = build_durable_offline_verification_export_bundle(
        service=service,
        proof_pack=pack,
        original_store=store,
    )
    assert bundle["independent_verification"]["valid"] is True
    exported = {
        evidence_id: base64.b64decode(item["content_base64"])
        for evidence_id, item in bundle["offline_evidence"].items()
    }
    assert set(exported) == expected_ids
    assert exported[outcome_evidence_id] == OUTCOME_BYTES
    for role, evidence_id in initial_ids.items():
        assert exported[evidence_id] == initial_originals[role]
    assert len(store.reads) == 4


def test_recovered_offline_export_fails_closed_if_final_outcome_original_is_missing_or_tampered(tmp_path):
    database = tmp_path / "recovered-offline-tamper.sqlite3"
    store = Store()
    service, finding_id, _initial_ids, _initial_originals = _seed_secure_actioned_case(database, store)
    outcome_evidence_id = _resolve_secure_outcome(service, database, store, finding_id)
    pack = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    outcome_item = next(
        item for item in pack["proof_manifest"]["evidence"]
        if item["evidence_id"] == outcome_evidence_id
    )
    outcome_key = next(
        key for key in store._stored
        if key[0].endswith(f"/{outcome_evidence_id}")
    )
    store._stored[outcome_key] = b"TAMPERED FINAL SETTLEMENT"
    with pytest.raises(AssuranceStoreError, match="sha256 mismatch"):
        build_durable_offline_verification_export_bundle(
            service=service,
            proof_pack=pack,
            original_store=store,
        )

    store._stored.pop(outcome_key)
    with pytest.raises(AssuranceStoreError, match="immutable original retrieval failed"):
        build_durable_offline_verification_export_bundle(
            service=service,
            proof_pack=pack,
            original_store=store,
        )
    assert outcome_item["hashes"]["sha256"] == hashlib.sha256(OUTCOME_BYTES).hexdigest()
