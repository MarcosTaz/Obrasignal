from __future__ import annotations

import base64
from datetime import date, datetime, timezone

from flask import Flask

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.intake_authorization import IntakeAuthorization, capture_authorized_original_evidence
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_externalization_audit import ProofExternalizationAuditStore
from vertical_apps.industrial_claims.proof_externalization_web import create_proof_externalization_blueprint
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.secure_case_intake import create_case_from_secure_capture
from vertical_apps.industrial_claims.service import IndustrialClaimsService


NOW = datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc)


class Store:
    name = "fake-compliance-worm"

    def __init__(self):
        self._stored: dict[tuple[str, str], bytes] = {}
        self.reads: list[tuple[str, str, str, str]] = []

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
        self.reads.append((tenant_id, evidence_id, object_ref, version_ref))
        return self._stored[(object_ref, version_ref)]


def _authorization() -> IntakeAuthorization:
    return IntakeAuthorization(
        authorization_id="auth-offline-export",
        tenant_id="tenant-a",
        case_ref="pilot-case-offline",
        authorized_by_ref="customer-authorizer@example.test",
        authorized_at="2026-09-01T18:00:00+00:00",
        expires_at="2026-09-02T18:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T18:00:00+00:00",
        transfer_channel_ref="secure-channel-offline",
        evidence_roles=("commercial_basis", "event", "cost"),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=1024 * 1024,
    )


def _capture_identity() -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id="tenant-a",
        actor_id="operator-a",
        subject="operator-subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _seed_secure_case(database, store: Store) -> tuple[IndustrialClaimsService, str, dict[str, bytes]]:
    service = IndustrialClaimsService(database)
    registry = SecureCaptureRegistry(database)
    payloads = {
        "commercial_basis": b"SECRET SIGNED COMMERCIAL BASIS",
        "event": b"SECRET CUSTOMER CHANGE EVENT",
        "cost": b"SECRET INCREMENTAL COST LEDGER",
    }
    refs = {
        "commercial_basis": "po-offline-1",
        "event": "change-offline-1",
        "cost": "ledger-offline-1",
    }
    evidence_ids: dict[str, str] = {}
    for role in ("commercial_basis", "event", "cost"):
        evidence_id = f"tenant-a:pilot-case-offline:{role}"
        captured = capture_authorized_original_evidence(
            authorization=_authorization(),
            evidence_role=role,
            original_store=store,
            evidence_id=evidence_id,
            identity=_capture_identity(),
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

    result = create_case_from_secure_capture(
        service,
        registry,
        tenant_id="tenant-a",
        actor_id="analyst-a",
        intake_case_ref="pilot-case-offline",
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
    return service, result.finding.finding_id, payloads


def _export_app(database, *, service, store, tenant_id="tenant-a") -> Flask:
    app = Flask(__name__)
    app.register_blueprint(
        create_proof_externalization_blueprint(
            service=service,
            audit_store=ProofExternalizationAuditStore(database),
            providers=ProofProviderBundle.fail_closed(),
            operator_identity=lambda: (tenant_id, "operator-a"),
            offline_export_identity=lambda: (tenant_id, "reviewer-a"),
            original_store=store,
        )
    )
    return app


def test_offline_export_route_releases_only_exact_secure_originals_after_target_confirmation(tmp_path):
    database = tmp_path / "offline-export-web.sqlite3"
    store = Store()
    service, finding_id, payloads = _seed_secure_case(database, store)
    proof = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
    target = proof["proof_manifest"]["attestation_target"]["sha256"]
    client = _export_app(database, service=service, store=store).test_client()

    exported = client.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={"confirm_confidential_export": True, "expected_target_sha256": target},
    )

    assert exported.status_code == 200
    assert exported.headers["Cache-Control"] == "no-store"
    assert exported.headers["Pragma"] == "no-cache"
    assert exported.headers["X-CausLedger-Confidential"] == "true"
    assert target[:16] in exported.headers["Content-Disposition"]
    body = exported.get_json()
    assert body["confidential"] is True
    assert body["truth_boundaries"]["must_not_be_published"] is True
    assert body["independent_verification"]["valid"] is True
    assert body["independent_verification"]["independently_verifiable_without_causledger"] is True
    decoded = {
        evidence_id: base64.b64decode(item["content_base64"])
        for evidence_id, item in body["offline_evidence"].items()
    }
    assert set(decoded.values()) == set(payloads.values())
    assert len(store.reads) == 3
    assert all(read[0] == "tenant-a" for read in store.reads)


def test_offline_export_route_fails_before_reading_originals_without_confirmation_or_exact_target(tmp_path):
    database = tmp_path / "offline-export-confirmation.sqlite3"
    store = Store()
    service, finding_id, _payloads = _seed_secure_case(database, store)
    proof = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
    target = proof["proof_manifest"]["attestation_target"]["sha256"]
    client = _export_app(database, service=service, store=store).test_client()

    missing = client.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={"expected_target_sha256": target},
    )
    assert missing.status_code == 422
    assert store.reads == []

    stale = client.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={"confirm_confidential_export": True, "expected_target_sha256": "0" * 64},
    )
    assert stale.status_code == 422
    assert "target changed" in stale.get_json()["message"]
    assert store.reads == []


def test_offline_export_route_is_tenant_scoped_and_never_reads_cross_tenant_originals(tmp_path):
    database = tmp_path / "offline-export-tenant.sqlite3"
    store = Store()
    service, finding_id, _payloads = _seed_secure_case(database, store)
    proof = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
    target = proof["proof_manifest"]["attestation_target"]["sha256"]
    tenant_b = _export_app(database, service=service, store=store, tenant_id="tenant-b").test_client()

    denied = tenant_b.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={"confirm_confidential_export": True, "expected_target_sha256": target},
    )
    assert denied.status_code == 422
    assert store.reads == []


def test_offline_export_route_refuses_legacy_hash_only_evidence(tmp_path):
    database = tmp_path / "offline-export-legacy.sqlite3"
    service = IndustrialClaimsService(database)
    finding_id = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="change-legacy",
        claim_family="NRE",
        commercial_basis_ref="po-legacy",
        cost_evidence_ref="ledger-legacy",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="legacy basis bytes were never persisted",
        event_evidence_content="legacy event bytes were never persisted",
        cost_evidence_content="legacy cost bytes were never persisted",
        notice_due=date(2026, 9, 30),
    ).finding.finding_id
    proof = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
    target = proof["proof_manifest"]["attestation_target"]["sha256"]
    store = Store()
    client = _export_app(database, service=service, store=store).test_client()

    denied = client.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={"confirm_confidential_export": True, "expected_target_sha256": target},
    )
    assert denied.status_code == 422
    assert "not durably persisted" in denied.get_json()["message"]
    assert store.reads == []


def test_offline_export_route_fails_closed_when_immutable_store_is_not_configured(tmp_path):
    database = tmp_path / "offline-export-unconfigured.sqlite3"
    store = Store()
    service, finding_id, _payloads = _seed_secure_case(database, store)
    proof = build_durable_claim_proof_pack(service, tenant_id="tenant-a", finding_id=finding_id)
    target = proof["proof_manifest"]["attestation_target"]["sha256"]
    client = _export_app(database, service=service, store=None).test_client()

    denied = client.post(
        f"/findings/{finding_id}/proof-pack/offline-export",
        json={"confirm_confidential_export": True, "expected_target_sha256": target},
    )
    assert denied.status_code == 422
    assert "not configured" in denied.get_json()["message"]
