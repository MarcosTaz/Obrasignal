from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.intake_authorization import IntakeAuthorization, capture_authorized_original_evidence
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.secure_case_intake import create_case_from_secure_capture
from vertical_apps.industrial_claims.service import IndustrialClaimsService


NOW = datetime(2026, 9, 1, 21, 45, tzinfo=timezone.utc)


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


def _authorization() -> IntakeAuthorization:
    return IntakeAuthorization(
        authorization_id="auth-proof-registry-1",
        tenant_id="tenant-a",
        case_ref="case-proof-registry-1",
        authorized_by_ref="customer-controller@example.test",
        authorized_at="2026-09-01T20:00:00+00:00",
        expires_at="2026-09-02T20:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T20:00:00+00:00",
        transfer_channel_ref="secure-intake-channel-1",
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


def _secure_case(database):
    store = Store()
    registry = SecureCaptureRegistry(database)
    refs = {
        "commercial_basis": "po-proof-registry",
        "event": "change-proof-registry",
        "cost": "ledger-proof-registry",
    }
    payloads = {
        "commercial_basis": b"signed purchase order terms",
        "event": b"customer directed engineering change",
        "cost": b"incremental engineering cost ledger",
    }
    evidence_ids: dict[str, str] = {}
    for role in ("commercial_basis", "event", "cost"):
        evidence_id = f"tenant-a:case-proof-registry-1:{role}"
        captured = capture_authorized_original_evidence(
            authorization=_authorization(),
            evidence_role=role,
            original_store=store,
            evidence_id=evidence_id,
            identity=_identity(),
            source_ref=refs[role],
            content=payloads[role],
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
        evidence_ids[role] = evidence_id

    service = IndustrialClaimsService(database)
    result = create_case_from_secure_capture(
        service,
        registry,
        tenant_id="tenant-a",
        actor_id="analyst-a",
        intake_case_ref="case-proof-registry-1",
        evidence_ids=evidence_ids,
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
    return service, result.finding.finding_id, evidence_ids


def test_secure_case_proof_rebinds_all_three_originals_to_one_append_only_registry_scope(tmp_path):
    database = tmp_path / "secure-case-proof-binding.sqlite3"
    service, finding_id, evidence_ids = _secure_case(database)

    pack = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    assert pack["self_verification"]["valid"] is True
    assert pack["core_package"]["truth_boundaries"]["secure_case_registry_binding_enforced_when_declared_secure"] is True
    assert {item["evidence_id"] for item in pack["proof_manifest"]["evidence"]} == set(evidence_ids.values())


def test_secure_case_proof_rejects_mutable_projection_metadata_drift_from_registry(tmp_path):
    database = tmp_path / "secure-case-proof-metadata-drift.sqlite3"
    service, finding_id, evidence_ids = _secure_case(database)
    build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    evidence_id = evidence_ids["event"]
    with sqlite3.connect(database) as conn:
        row = conn.execute(
            "SELECT metadata_json FROM evidence WHERE tenant_id=? AND evidence_id=?",
            ("tenant-a", evidence_id),
        ).fetchone()
        metadata = json.loads(row[0])
        metadata["intake_case_ref"] = "attacker-substituted-case"
        conn.execute(
            "UPDATE evidence SET metadata_json=? WHERE tenant_id=? AND evidence_id=?",
            (json.dumps(metadata, sort_keys=True, separators=(",", ":")), "tenant-a", evidence_id),
        )
        conn.commit()

    with pytest.raises(AssuranceStoreError, match="secure case registry metadata drift"):
        build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)


def test_secure_case_proof_rejects_projection_digest_drift_from_append_only_registry(tmp_path):
    database = tmp_path / "secure-case-proof-digest-drift.sqlite3"
    service, finding_id, evidence_ids = _secure_case(database)
    build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    evidence_id = evidence_ids["cost"]
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE evidence SET content_hash=? WHERE tenant_id=? AND evidence_id=?",
            ("0" * 64, "tenant-a", evidence_id),
        )
        conn.commit()

    with pytest.raises(AssuranceStoreError, match="secure case registry digest drift"):
        build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)


def test_secure_case_proof_rejects_mixed_secure_and_nonsecure_custody_after_persistence(tmp_path):
    database = tmp_path / "secure-case-proof-mixed-custody.sqlite3"
    service, finding_id, evidence_ids = _secure_case(database)
    build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)

    evidence_id = evidence_ids["commercial_basis"]
    with sqlite3.connect(database) as conn:
        row = conn.execute(
            "SELECT metadata_json FROM evidence WHERE tenant_id=? AND evidence_id=?",
            ("tenant-a", evidence_id),
        ).fetchone()
        metadata = json.loads(row[0])
        metadata.pop("capture_mode", None)
        metadata["raw_content_persisted"] = False
        conn.execute(
            "UPDATE evidence SET metadata_json=? WHERE tenant_id=? AND evidence_id=?",
            (json.dumps(metadata, sort_keys=True, separators=(",", ":")), "tenant-a", evidence_id),
        )
        conn.commit()

    with pytest.raises(AssuranceStoreError, match="mixes secure and non-secure case evidence custody"):
        build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
