from auth_context import RequestIdentity
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


def _payload(**overrides):
    payload = {
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "cancel-1",
        "claim_family": "TOOLING",
        "commercial_basis_ref": "basis-1",
        "cost_evidence_ref": "cost-1",
        "gross_cost": "10000",
        "currency": "EUR",
        "commercial_basis_content": "signed tooling agreement",
        "event_evidence_content": "documented cancellation event",
        "cost_evidence_content": "cost ledger supporting 10000 EUR exposure",
        "notice_deadline_not_applicable": True,
    }
    payload.update(overrides)
    return payload


def test_http_amendment_is_analyst_only_and_requires_fresh_review(tmp_path):
    database = tmp_path / "amendment-web.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-1", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer-1", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator-1", "operator")).test_client()

    created = analyst.post("/analyze", json=_payload())
    assert created.status_code == 201
    first_id = created.get_json()["finding_id"]

    denied_reviewer = reviewer.post(
        f"/findings/{first_id}/amend",
        json=_payload(cost_evidence_ref="cost-2", gross_cost="12000", cost_evidence_content="corrected ledger"),
    )
    denied_operator = operator.post(
        f"/findings/{first_id}/amend",
        json=_payload(cost_evidence_ref="cost-2", gross_cost="12000", cost_evidence_content="corrected ledger"),
    )
    assert denied_reviewer.status_code == 403
    assert denied_operator.status_code == 403

    amended = analyst.post(
        f"/findings/{first_id}/amend",
        json=_payload(
            cost_evidence_ref="cost-2",
            gross_cost="12000",
            cost_evidence_content="corrected ledger supporting 12000 EUR exposure",
        ),
    )
    assert amended.status_code == 201
    body = amended.get_json()
    assert body["finding_id"] != first_id
    assert body["revision"] == 2
    assert body["supersedes_finding_id"] == first_id
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["requires_fresh_review"] is True
    assert body["customer_contact_authorized"] is False
    assert body["external_claim_submission_authorized"] is False

    historical = analyst.get(f"/findings/{first_id}")
    current = analyst.get(f"/findings/{body['finding_id']}")
    assert historical.status_code == 200
    assert current.status_code == 200
    assert historical.get_json()["revision"]["is_current"] is False
    assert current.get_json()["revision"]["is_current"] is True
    assert current.get_json()["revision"]["number"] == 2


def test_http_amendment_is_tenant_scoped_and_identity_fields_are_immutable(tmp_path):
    database = tmp_path / "amendment-tenant.sqlite3"
    alpha = create_app(database, identity_resolver=_identity("alpha", "alpha-analyst", "analyst")).test_client()
    beta = create_app(database, identity_resolver=_identity("beta", "beta-analyst", "analyst")).test_client()

    created = alpha.post("/analyze", json=_payload())
    first_id = created.get_json()["finding_id"]

    cross_tenant = beta.post(
        f"/findings/{first_id}/amend",
        json=_payload(cost_evidence_ref="cost-2", gross_cost="12000", cost_evidence_content="beta guessed correction"),
    )
    assert cross_tenant.status_code == 422
    assert "tenant-scoped" in cross_tenant.get_json()["message"]

    changed_identity = alpha.post(
        f"/findings/{first_id}/amend",
        json=_payload(customer_ref="other-oem", cost_evidence_ref="cost-2", gross_cost="12000", cost_evidence_content="corrected ledger"),
    )
    assert changed_identity.status_code == 422
    assert "cannot change recovery fingerprint identity fields" in changed_identity.get_json()["message"]

    detail = alpha.get(f"/findings/{first_id}")
    assert detail.status_code == 200
    assert detail.get_json()["revision"]["is_current"] is True
    assert detail.get_json()["revision"]["number"] == 1
