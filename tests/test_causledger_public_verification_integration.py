from __future__ import annotations

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _payload():
    return {
        "customer_ref": "confidential-oem",
        "program_ref": "confidential-program",
        "event_ref": "change-17",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-confidential-1",
        "cost_evidence_ref": "ledger-confidential-1",
        "currency": "EUR",
        "commercial_basis_content": "signed commercial basis",
        "event_evidence_content": "customer-directed engineering change",
        "cost_evidence_content": "engineering cost ledger",
        "gross_cost": "15000",
        "notice_due": "2026-09-30",
    }


def test_real_app_publication_is_operator_only_and_public_result_is_minimized(tmp_path):
    database = tmp_path / "causledger.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("tenant-a", "reviewer-a", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("tenant-a", "operator-a", "operator")).test_client()

    created = analyst.post("/analyze", json=_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]

    analyst_denied = analyst.post(
        f"/findings/{finding_id}/public-verification",
        json={"confirm_publication": True},
    )
    reviewer_denied = reviewer.post(
        f"/findings/{finding_id}/public-verification",
        json={"confirm_publication": True},
    )
    assert analyst_denied.status_code == 403
    assert reviewer_denied.status_code == 403
    assert analyst_denied.get_json() == {"error": "authorization_denied"}
    assert reviewer_denied.get_json() == {"error": "authorization_denied"}

    published = operator.post(
        f"/findings/{finding_id}/public-verification",
        json={"confirm_publication": True},
    )
    assert published.status_code == 201
    publication = published.get_json()
    assert publication["private_case_fields_published"] is False
    assert publication["external_claim_submission_performed"] is False
    token = publication["verification_id"]

    public = operator.get(f"/verify/{token}")
    assert public.status_code == 200
    rendered = repr(public.get_json())
    for secret in (
        "tenant-a",
        finding_id,
        "confidential-oem",
        "confidential-program",
        "po-confidential-1",
        "ledger-confidential-1",
        "15000",
    ):
        assert secret not in rendered
    assert public.headers["Cache-Control"] == "no-store"


def test_real_app_public_lifecycle_mutation_remains_tenant_scoped(tmp_path):
    database = tmp_path / "causledger.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    operator_a = create_app(database, identity_resolver=_identity("tenant-a", "operator-a", "operator")).test_client()
    operator_b = create_app(database, identity_resolver=_identity("tenant-b", "operator-b", "operator")).test_client()

    finding_id = analyst.post("/analyze", json=_payload()).get_json()["finding_id"]
    token = operator_a.post(
        f"/findings/{finding_id}/public-verification",
        json={"confirm_publication": True},
    ).get_json()["verification_id"]

    attacked = operator_b.post(
        f"/verify/{token}/withdraw",
        json={"confirm_withdrawal": True, "reason": "cross-tenant attempt"},
    )
    assert attacked.status_code == 422
    assert "does not belong to authenticated tenant" in attacked.get_json()["message"]
    assert operator_a.get(f"/verify/{token}").get_json()["current_lifecycle"]["state"] == "CURRENT"

    withdrawn = operator_a.post(
        f"/verify/{token}/withdraw",
        json={"confirm_withdrawal": True, "reason": "proof publication withdrawn by owner"},
    )
    assert withdrawn.status_code == 200
    assert operator_a.get(f"/verify/{token}").get_json()["current_lifecycle"]["state"] == "WITHDRAWN"
