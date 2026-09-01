from __future__ import annotations

from datetime import datetime, timezone

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.outcome_authorization import OutcomeEvidenceAuthorization, capture_authorized_outcome_evidence
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


NOW = datetime(2026, 9, 1, 20, 30, tzinfo=timezone.utc)


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


def _actioned_case(database, *, tenant_id="tenant-a", suffix="1"):
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id=tenant_id,
        actor_id="analyst-a",
        customer_ref=f"oem-{suffix}",
        program_ref=f"program-{suffix}",
        event_ref=f"change-{suffix}",
        claim_family="NRE",
        commercial_basis_ref=f"po-{suffix}",
        cost_evidence_ref=f"ledger-{suffix}",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="synthetic purchase order terms",
        event_evidence_content="synthetic customer change",
        cost_evidence_content="synthetic cost ledger",
        notice_deadline_not_applicable=True,
    )
    finding_id = result.finding.finding_id
    service.review(
        tenant_id=tenant_id,
        finding_id=finding_id,
        reviewer="reviewer-b",
        approved=True,
        reason="synthetic independent review",
    )
    service.action(tenant_id=tenant_id, finding_id=finding_id, actor_id="operator-a")
    return finding_id


def _capture_outcome(database, finding_id: str, *, tenant_id="tenant-a", suffix="1"):
    registry = SecureOutcomeRegistry(database)
    authorization = OutcomeEvidenceAuthorization(
        authorization_id=f"outcome-auth-{suffix}",
        tenant_id=tenant_id,
        finding_id=finding_id,
        authorized_by_ref="customer-controller@example.test",
        authorized_at="2026-09-01T20:00:00+00:00",
        expires_at="2026-09-02T20:00:00+00:00",
        minimum_immutable_retention_until="2027-09-02T20:00:00+00:00",
        transfer_channel_ref=f"secure-outcome-channel-{suffix}",
        data_terms_state="SIGNED",
        immutable_retention_acknowledged=True,
        max_bytes=1024 * 1024,
    )
    evidence_id = f"{tenant_id}:outcome:payment-{suffix}"
    captured = capture_authorized_outcome_evidence(
        authorization=authorization,
        original_store=Store(),
        evidence_id=evidence_id,
        identity=CaptureIdentity(
            tenant_id=tenant_id,
            actor_id="operator-a",
            subject="operator-subject-a",
            amr=("webauthn",),
            session_ref="session-a",
            request_ref="request-a",
        ),
        source_ref=f"bank-settlement-{suffix}",
        content=f"SECRET-SETTLEMENT-BODY-{suffix}".encode(),
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


def _resolve_payload(evidence_id: str, *, suffix="1"):
    return {
        "outcome_id": f"payment-{suffix}",
        "recovered_amount": "7500",
        "currency": "EUR",
        "evidence_id": evidence_id,
        "evidence_ref": f"bank-settlement-{suffix}",
        "final_cumulative": True,
    }


def test_secure_resolve_is_operator_only_id_only_and_leaks_no_outcome_bytes(tmp_path):
    database = tmp_path / "secure-outcome-web.sqlite3"
    finding_id = _actioned_case(database)
    evidence = _capture_outcome(database, finding_id)
    client = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "operator-c", "operator"),
    ).test_client()

    response = client.post(f"/findings/{finding_id}/secure-resolve", json=_resolve_payload(evidence.evidence_id))
    assert response.status_code == 201
    body = response.get_json()
    assert body["finding_id"] == finding_id
    assert body["evidence_ref"] == evidence.evidence_id
    assert body["final_cumulative"] is True
    assert body["finding_closed_by_outcome"] is True
    assert body["evidence_custody_state"] == "AUTHORIZED_IMMUTABLE_ORIGINAL"
    assert body["verification_state"] == "CONTENT_HASHED"
    assert body["source_authentication_state"] == "UNVERIFIED"
    assert body["raw_document_content_included"] is False
    assert "SECRET-SETTLEMENT-BODY" not in response.get_data(as_text=True)

    detail = client.get(f"/findings/{finding_id}")
    assert detail.status_code == 200
    detail_body = detail.get_json()
    assert detail_body["finding"]["state"] == "RESOLVED"
    assert detail_body["outcomes"][0]["evidence"]["evidence_id"] == evidence.evidence_id
    assert "SECRET-SETTLEMENT-BODY" not in detail.get_data(as_text=True)


def test_secure_resolve_rejects_raw_content_even_in_synthetic_inline_mode(tmp_path):
    database = tmp_path / "secure-outcome-web-raw.sqlite3"
    finding_id = _actioned_case(database)
    evidence = _capture_outcome(database, finding_id)
    client = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "operator-c", "operator"),
        allow_inline_evidence_content=True,
    ).test_client()
    payload = _resolve_payload(evidence.evidence_id)
    payload["evidence_content"] = "attempted raw bypass"

    denied = client.post(f"/findings/{finding_id}/secure-resolve", json=payload)
    assert denied.status_code == 422
    assert "evidence id only" in denied.get_json()["message"]
    detail = IndustrialClaimsService(database).read_model.get_finding(tenant_id="tenant-a", finding_id=finding_id)
    assert detail["finding"]["state"] == "ACTIONED"
    assert detail["outcomes"] == []


def test_secure_resolve_rejects_non_operator_before_mutation(tmp_path):
    database = tmp_path / "secure-outcome-web-role.sqlite3"
    finding_id = _actioned_case(database)
    evidence = _capture_outcome(database, finding_id)
    analyst = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "analyst-a", "analyst"),
    ).test_client()

    denied = analyst.post(f"/findings/{finding_id}/secure-resolve", json=_resolve_payload(evidence.evidence_id))
    assert denied.status_code == 403
    detail = IndustrialClaimsService(database).read_model.get_finding(tenant_id="tenant-a", finding_id=finding_id)
    assert detail["finding"]["state"] == "ACTIONED"


def test_secure_resolve_cannot_consume_other_tenant_outcome_evidence(tmp_path):
    database = tmp_path / "secure-outcome-web-tenant.sqlite3"
    tenant_a_finding = _actioned_case(database, tenant_id="tenant-a", suffix="a")
    evidence = _capture_outcome(database, tenant_a_finding, tenant_id="tenant-a", suffix="a")
    tenant_b_finding = _actioned_case(database, tenant_id="tenant-b", suffix="b")
    tenant_b = create_app(
        database,
        identity_resolver=_request_identity("tenant-b", "operator-b", "operator"),
    ).test_client()

    denied = tenant_b.post(
        f"/findings/{tenant_b_finding}/secure-resolve",
        json=_resolve_payload(evidence.evidence_id, suffix="a"),
    )
    assert denied.status_code == 422
    detail = IndustrialClaimsService(database).read_model.get_finding(
        tenant_id="tenant-b",
        finding_id=tenant_b_finding,
    )
    assert detail["finding"]["state"] == "ACTIONED"
    assert detail["outcomes"] == []


def test_legacy_resolve_remains_fail_closed_without_inline_opt_in(tmp_path):
    database = tmp_path / "legacy-resolve-closed.sqlite3"
    finding_id = _actioned_case(database)
    client = create_app(
        database,
        identity_resolver=_request_identity("tenant-a", "operator-c", "operator"),
    ).test_client()

    denied = client.post(
        f"/findings/{finding_id}/resolve",
        json={
            "outcome_id": "payment-legacy",
            "recovered_amount": "7500",
            "currency": "EUR",
            "evidence_ref": "legacy-proof",
            "evidence_content": "inline settlement proof",
            "final_cumulative": True,
        },
    )
    assert denied.status_code == 422
    assert "inline documentary content is disabled" in denied.get_json()["message"]
