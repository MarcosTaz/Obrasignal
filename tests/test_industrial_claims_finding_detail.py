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
        "customer_ref": "SECRET-CUSTOMER-ALPHA",
        "program_ref": "SECRET-PROGRAM-ALPHA",
        "event_ref": "SECRET-EVENT-ALPHA",
        "claim_family": "WIP",
        "commercial_basis_ref": "basis-alpha",
        "cost_evidence_ref": "cost-alpha",
        "currency": "EUR",
        "commercial_basis_content": "SECRET RAW COMMERCIAL DOCUMENT",
        "event_evidence_content": "SECRET RAW EVENT DOCUMENT",
        "cost_evidence_content": "SECRET RAW COST DOCUMENT",
        "gross_cost": "10000",
        "avoided_cost": "1000",
        "prior_payment": "500",
        "notice_due": "2026-09-30",
    }


def test_finding_detail_is_tenant_scoped_and_does_not_leak_cross_tenant_case(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    alpha = create_app(database, identity_resolver=_identity("alpha", "analyst-a", "analyst")).test_client()
    beta = create_app(database, identity_resolver=_identity("beta", "analyst-b", "analyst")).test_client()

    created = alpha.post("/analyze", json=_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]

    own = alpha.get(f"/findings/{finding_id}")
    assert own.status_code == 200
    own_body = own.get_json()
    assert own_body["case"]["finding_id"] == finding_id
    assert own_body["case"]["customer_ref"] == "SECRET-CUSTOMER-ALPHA"
    assert own_body["case"]["notice_deadline_state"] == "DECLARED_DATE_FOR_REVIEW"
    assert own_body["notice"] == {"truth_state": "DECLARED_DATE_FOR_REVIEW", "due_date": "2026-09-30"}
    assert own_body["raw_document_content_included"] is False
    serialized = own.get_data(as_text=True)
    assert "SECRET RAW COMMERCIAL DOCUMENT" not in serialized
    assert "SECRET RAW EVENT DOCUMENT" not in serialized
    assert "SECRET RAW COST DOCUMENT" not in serialized

    denied = beta.get(f"/findings/{finding_id}")
    assert denied.status_code == 422
    denied_text = denied.get_data(as_text=True)
    assert "SECRET-CUSTOMER-ALPHA" not in denied_text
    assert "SECRET-PROGRAM-ALPHA" not in denied_text
    assert "SECRET-EVENT-ALPHA" not in denied_text
    assert "SECRET RAW" not in denied_text


def test_finding_detail_requires_verified_authorized_identity(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    unauthenticated = create_app(database).test_client()
    viewer = create_app(database, identity_resolver=_identity("alpha", "viewer", "viewer")).test_client()

    assert unauthenticated.get("/findings/unknown").status_code == 401
    assert viewer.get("/findings/unknown").status_code == 403


def test_path_finding_ids_reach_bounded_handler_instead_of_route_404(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-a", "analyst")).test_client()

    response = analyst.get("/findings/nonexistent/nested/id")
    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]
    assert "not found" in body["message"].lower()
