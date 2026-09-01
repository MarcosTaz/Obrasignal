from __future__ import annotations

import json
from datetime import datetime, timezone

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.intake_authorization import IntakeAuthorization, capture_authorized_original_evidence
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


NOW = datetime(2026, 9, 1, 19, 45, tzinfo=timezone.utc)


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


def _request_identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _authorization(*, auth_id: str, tenant_id: str = "tenant-a") -> IntakeAuthorization:
    return IntakeAuthorization(
        authorization_id=auth_id,
        tenant_id=tenant_id,
        case_ref="pilot-case-001",
        authorized_by_ref="customer-authorizer@example.test",
        authorized_at="2026-09-01T18:00:00+00:00",
        expires_at="2026-09-02T18:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T18:00:00+00:00",
        transfer_channel_ref=f"secure-channel-{auth_id}",
        evidence_roles=("commercial_basis", "event", "cost"),
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes_per_evidence=1024 * 1024,
    )


def _capture_identity(tenant_id: str = "tenant-a") -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id=tenant_id,
        actor_id="operator-a",
        subject="operator-subject-a",
        amr=("webauthn",),
        session_ref="session-a",
        request_ref="request-a",
    )


def _seed_triplet(database, *, suffix: str, auth_id: str, tenant_id: str = "tenant-a") -> dict[str, str]:
    registry = SecureCaptureRegistry(database)
    store = Store()
    definitions = {
        "commercial_basis": ("po-1", f"SECRET-PO-BODY-{suffix}".encode()),
        "event": ("change-17", f"SECRET-EVENT-BODY-{suffix}".encode()),
        "cost": (f"ledger-{suffix}", f"SECRET-COST-BODY-{suffix}".encode()),
    }
    result: dict[str, str] = {}
    for role, (source_ref, content) in definitions.items():
        evidence_id = f"{tenant_id}:pilot-case-001:{suffix}:{role}"
        captured = capture_authorized_original_evidence(
            authorization=_authorization(auth_id=auth_id, tenant_id=tenant_id),
            evidence_role=role,
            original_store=store,
            evidence_id=evidence_id,
            identity=_capture_identity(tenant_id),
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
        result[role] = evidence_id
    return result


def _payload(ids: dict[str, str], *, suffix: str = "r1") -> dict:
    return {
        "intake_case_ref": "pilot-case-001",
        "evidence_ids": ids,
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "change-17",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-1",
        "cost_evidence_ref": f"ledger-{suffix}",
        "gross_cost": "10000" if suffix == "r1" else "12000",
        "currency": "EUR",
        "notice_deadline_not_applicable": True,
    }


def test_secure_analyze_accepts_only_registered_ids_and_never_returns_original_bytes(tmp_path):
    database = tmp_path / "secure-web.sqlite3"
    ids = _seed_triplet(database, suffix="r1", auth_id="auth-r1")
    client = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "analyst-a", "analyst"),
    ).test_client()

    created = client.post("/secure-analyze", json=_payload(ids))
    assert created.status_code == 201
    body = created.get_json()
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["evidence_custody_state"] == "AUTHORIZED_IMMUTABLE_ORIGINALS"
    assert body["raw_document_content_included"] is False
    assert set(body["source_authentication_states"].values()) == {"UNVERIFIED"}

    finding_id = body["finding_id"]
    detail = client.get(f"/findings/{finding_id}")
    assert detail.status_code == 200
    assert detail.get_json()["raw_document_content_included"] is False
    assert "SECRET-" not in detail.get_data(as_text=True)

    proof = client.get(f"/findings/{finding_id}/proof-pack")
    assert proof.status_code == 200
    assert "SECRET-" not in proof.get_data(as_text=True)


def test_secure_route_rejects_raw_document_fields_even_when_synthetic_inline_mode_is_enabled(tmp_path):
    database = tmp_path / "secure-web-raw.sqlite3"
    ids = _seed_triplet(database, suffix="r1", auth_id="auth-r1")
    client = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "analyst-a", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()
    payload = _payload(ids)
    payload["cost_evidence_content"] = "attempted raw bypass"

    denied = client.post("/secure-analyze", json=payload)
    assert denied.status_code == 422
    assert "evidence ids only" in denied.get_json()["message"]
    assert IndustrialClaimsService(database).store.count("findings", "tenant-a") == 0


def test_secure_route_derives_tenant_from_verified_identity_and_blocks_cross_tenant_ids(tmp_path):
    database = tmp_path / "secure-web-tenant.sqlite3"
    ids = _seed_triplet(database, suffix="r1", auth_id="auth-r1", tenant_id="tenant-a")
    tenant_b = create_app(
        database,
        identity_resolver=_request_identity("tenant-b", "analyst-b", "analyst"),
    ).test_client()

    denied = tenant_b.post("/secure-analyze", json=_payload(ids))
    assert denied.status_code == 422
    assert IndustrialClaimsService(database).store.count("findings", "tenant-a") == 0
    assert IndustrialClaimsService(database).store.count("findings", "tenant-b") == 0


def test_secure_amend_route_creates_fresh_revision_from_new_registered_ids(tmp_path):
    database = tmp_path / "secure-web-amend.sqlite3"
    first_ids = _seed_triplet(database, suffix="r1", auth_id="auth-r1")
    client = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "analyst-a", "analyst"),
    ).test_client()
    first = client.post("/secure-analyze", json=_payload(first_ids))
    assert first.status_code == 201
    old_id = first.get_json()["finding_id"]

    second_ids = _seed_triplet(database, suffix="r2", auth_id="auth-r2")
    amended = client.post(f"/findings/{old_id}/secure-amend", json=_payload(second_ids, suffix="r2"))
    assert amended.status_code == 201
    body = amended.get_json()
    assert body["revision"] == 2
    assert body["supersedes_finding_id"] == old_id
    assert body["finding_id"] != old_id
    assert body["requires_fresh_review"] is True
    assert body["evidence_custody_state"] == "AUTHORIZED_IMMUTABLE_ORIGINALS"
    assert body["raw_document_content_included"] is False

    old_detail = client.get(f"/findings/{old_id}").get_json()
    new_detail = client.get(f"/findings/{body['finding_id']}").get_json()
    assert old_detail["revision"]["is_current"] is False
    assert new_detail["revision"]["revision"] == 2
    assert new_detail["finding"]["reviewer"] is None
    assert "SECRET-" not in json.dumps(new_detail)
