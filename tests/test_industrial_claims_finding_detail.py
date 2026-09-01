from datetime import date

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app as _create_app


def create_app(*args, **kwargs):
    kwargs.setdefault("allow_inline_evidence_content", True)
    return _create_app(*args, **kwargs)


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
    assert own_body["notice"]["truth_state"] == "DECLARED_DATE_FOR_REVIEW"
    assert own_body["notice"]["due_date"] == "2026-09-30"
    assert own_body["notice"]["timing_establishes_recoverability"] is False
    assert own_body["notice"]["expired_establishes_nonrecoverability"] is False
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


def test_notice_timing_exposes_operational_risk_without_deciding_recoverability(tmp_path):
    database = tmp_path / "deadline-timing.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-a", "analyst")).test_client()
    created = analyst.post("/analyze", json=_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]
    read_model = IndustrialClaimsReadModel(database)

    open_detail = read_model.get_finding(tenant_id="alpha", finding_id=finding_id, as_of_date=date(2026, 9, 29))
    due_detail = read_model.get_finding(tenant_id="alpha", finding_id=finding_id, as_of_date=date(2026, 9, 30))
    expired_detail = read_model.get_finding(tenant_id="alpha", finding_id=finding_id, as_of_date=date(2026, 10, 1))

    assert open_detail["notice"]["timing_state"] == "OPEN"
    assert due_detail["notice"]["timing_state"] == "DUE_TODAY"
    assert expired_detail["notice"]["timing_state"] == "EXPIRED"
    assert expired_detail["notice"]["expired_requires_human_exception_or_waiver_review"] is True
    assert expired_detail["notice"]["expired_establishes_nonrecoverability"] is False
    assert expired_detail["notice"]["timing_establishes_recoverability"] is False
    assert expired_detail["finding"]["state"] == "READY_FOR_REVIEW"


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


def test_historical_revision_detail_exposes_direct_successor_and_current_finding(tmp_path):
    database = tmp_path / "revision-navigation.sqlite3"
    service = IndustrialClaimsService(database)
    first = service.analyze(
        tenant_id="alpha", actor_id="analyst-1", customer_ref="oem-1", program_ref="program-1",
        event_ref="cancel-1", claim_family="TOOLING", commercial_basis_ref="basis-1", cost_evidence_ref="cost-1",
        gross_cost="10000", currency="EUR", commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event", cost_evidence_content="cost ledger v1",
        notice_deadline_not_applicable=True,
    )
    second = amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-2",
        customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1", claim_family="TOOLING",
        commercial_basis_ref="basis-1", cost_evidence_ref="cost-2", gross_cost="12000", currency="EUR",
        commercial_basis_content="signed tooling agreement", event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger v2", notice_deadline_not_applicable=True,
    )
    third = amend_case(
        service, tenant_id="alpha", finding_id=second.finding.finding_id, actor_id="analyst-3",
        customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1", claim_family="TOOLING",
        commercial_basis_ref="basis-1", cost_evidence_ref="cost-3", gross_cost="13000", currency="EUR",
        commercial_basis_content="signed tooling agreement", event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger v3", notice_deadline_not_applicable=True,
    )

    read_model = IndustrialClaimsReadModel(database)
    first_detail = read_model.get_finding(tenant_id="alpha", finding_id=first.finding.finding_id)
    second_detail = read_model.get_finding(tenant_id="alpha", finding_id=second.finding.findinding_id) if False else read_model.get_finding(tenant_id="alpha", finding_id=second.finding.finding_id)
    third_detail = read_model.get_finding(tenant_id="alpha", finding_id=third.finding.finding_id)

    assert first_detail["revision"]["superseded_by_finding_id"] == second.finding.finding_id
    assert first_detail["revision"]["current_finding_id"] == third.finding.finding_id
    assert second_detail["revision"]["superseded_by_finding_id"] == third.finding.finding_id
    assert second_detail["revision"]["current_finding_id"] == third.finding.finding_id
    assert third_detail["revision"]["superseded_by_finding_id"] is None
    assert third_detail["revision"]["current_finding_id"] == third.finding.finding_id
