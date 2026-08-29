from auth_context import RequestIdentity
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


def _documents():
    return dict(
        commercial_basis_content="signed supply agreement with documented cancellation allocation terms",
        event_evidence_content="customer cancellation notice tied to the program",
        cost_evidence_content="inventory ledger and supplier commitment detail",
    )


def _analyze(service: IndustrialClaimsService, tenant_id: str, event_ref: str, actor_id: str = "analyst"):
    return service.analyze(
        tenant_id=tenant_id,
        actor_id=actor_id,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref=event_ref,
        claim_family="WIP",
        commercial_basis_ref=f"basis-{event_ref}",
        cost_evidence_ref=f"cost-{event_ref}",
        gross_cost="10000",
        prior_payment="1000",
        notice_deadline_not_applicable=True,
        **_documents(),
    )


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def test_read_model_is_bounded_tenant_scoped_and_exposes_no_raw_document_content(tmp_path):
    database = tmp_path / "queue.sqlite3"
    service = IndustrialClaimsService(database)
    alpha = _analyze(service, "alpha", "cancel-alpha")
    _analyze(service, "beta", "cancel-beta")

    read_model = IndustrialClaimsReadModel(database)
    items = read_model.list_findings(tenant_id="alpha", states=("READY_FOR_REVIEW",), limit=10)

    assert len(items) == 1
    item = items[0]
    assert item.finding_id == alpha.finding.finding_id
    assert item.state == "READY_FOR_REVIEW"
    assert item.net_potential == "9000"
    assert item.currency_unit == "currency"
    assert item.creator_actor == "analyst"
    assert item.reviewer is None
    serialized = str(item.as_dict())
    assert "signed supply agreement" not in serialized
    assert "customer cancellation notice" not in serialized
    assert "inventory ledger" not in serialized


def test_reviewer_and_operator_receive_only_actionable_role_scoped_states(tmp_path):
    database = tmp_path / "queue-api.sqlite3"
    service = IndustrialClaimsService(database)
    result = _analyze(service, "alpha", "cancel-queue", actor_id="analyst-1")
    finding_id = result.finding.finding_id

    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer-1", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator-1", "operator")).test_client()
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-1", "analyst")).test_client()

    analyst_queue = analyst.get("/findings")
    assert analyst_queue.status_code == 403

    reviewer_queue = reviewer.get("/findings")
    assert reviewer_queue.status_code == 200
    reviewer_body = reviewer_queue.get_json()
    assert reviewer_body["queue_scope"] == ["READY_FOR_REVIEW"]
    assert reviewer_body["count"] == 1
    assert reviewer_body["findings"][0]["finding_id"] == finding_id

    assert operator.get("/findings").get_json()["count"] == 0

    reviewed = reviewer.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "documentary evidence and net potential reviewed"},
    )
    assert reviewed.status_code == 200

    operator_queue = operator.get("/findings")
    assert operator_queue.status_code == 200
    operator_body = operator_queue.get_json()
    assert operator_body["queue_scope"] == ["ACTIONED", "APPROVED"]
    assert operator_body["count"] == 1
    assert operator_body["findings"][0]["state"] == "APPROVED"

    reviewer_after = reviewer.get("/findings")
    assert reviewer_after.get_json()["count"] == 0


def test_queue_cannot_cross_tenant_or_request_another_roles_state(tmp_path):
    database = tmp_path / "queue-isolation.sqlite3"
    service = IndustrialClaimsService(database)
    _analyze(service, "alpha", "alpha-only")
    _analyze(service, "beta", "beta-only")

    beta_reviewer = create_app(database, identity_resolver=_identity("beta", "reviewer-b", "reviewer")).test_client()
    body = beta_reviewer.get("/findings").get_json()
    assert body["count"] == 1
    assert all(item["finding_id"].startswith("beta:") for item in body["findings"])

    forbidden_state = beta_reviewer.get("/findings?state=APPROVED")
    assert forbidden_state.status_code == 403
    assert forbidden_state.get_json() == {"error": "authorization_denied"}


def test_queue_limit_is_bounded_and_invalid_limit_fails_closed(tmp_path):
    database = tmp_path / "queue-limit.sqlite3"
    service = IndustrialClaimsService(database)
    _analyze(service, "alpha", "one")
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer", "reviewer")).test_client()

    invalid = reviewer.get("/findings?limit=101")
    assert invalid.status_code == 422
    assert "limit" in invalid.get_json()["message"]

    malformed = reviewer.get("/findings?limit=abc")
    assert malformed.status_code == 422
    assert "integer" in malformed.get_json()["message"]
