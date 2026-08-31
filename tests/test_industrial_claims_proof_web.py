from __future__ import annotations

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


def test_authenticated_tenant_can_export_current_durable_proof_pack(tmp_path):
    database = tmp_path / "claims.db"
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="customer-1",
        program_ref="program-1",
        event_ref="change-R17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="timesheet-1",
        gross_cost="5000",
        currency="EUR",
        commercial_basis_content="Commercial basis",
        event_evidence_content="Customer requested change R17",
        cost_evidence_content="Engineering cost support",
        notice_deadline_not_applicable=True,
    )
    identity = RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject="analyst-a",
        claims={"roles": ["analyst"]},
    )
    app = create_app(database, identity_resolver=lambda: identity)
    client = app.test_client()

    response = client.get(f"/findings/{result.finding.finding_id}/proof-pack")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["brand"] == "CausLedger"
    assert payload["self_verification"]["valid"] is True
    assert payload["core_package"]["tenant_id"] == "tenant-a"
    assert payload["core_package"]["finding"]["finding_id"] == result.finding.finding_id


def test_cross_tenant_header_cannot_export_proof_pack(tmp_path):
    database = tmp_path / "claims.db"
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="customer-1",
        program_ref="program-1",
        event_ref="change-R17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="timesheet-1",
        gross_cost="5000",
        currency="EUR",
        commercial_basis_content="Commercial basis",
        event_evidence_content="Customer requested change R17",
        cost_evidence_content="Engineering cost support",
        notice_deadline_not_applicable=True,
    )
    identity = RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject="analyst-a",
        claims={"roles": ["analyst"]},
    )
    app = create_app(database, identity_resolver=lambda: identity)
    client = app.test_client()

    response = client.get(
        f"/findings/{result.finding.finding_id}/proof-pack",
        headers={"X-Tenant-ID": "tenant-b"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "identity_scope_mismatch"
