from auth_context import RequestIdentity
from vertical_apps.industrial_claims.service import NOTICE_DEADLINE_EVIDENCE
from vertical_apps.industrial_claims.web import create_app


def _payload():
    return {
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "cancel-1",
        "claim_family": "WIP",
        "commercial_basis_ref": "po-1",
        "cost_evidence_ref": "ledger-1",
        "gross_cost": "10000",
        "avoided_cost": "1000",
        "prior_payment": "500",
        "notice_due": "2026-09-30",
    }


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def test_analyze_rejects_unverified_raw_identity_headers(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3").test_client()
    response = client.post(
        "/analyze",
        headers={"X-Tenant-ID": "alpha", "X-Actor-ID": "analyst"},
        json=_payload(),
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}


def test_verified_identity_without_required_role_is_forbidden(tmp_path):
    client = create_app(
        tmp_path / "industrial.sqlite3",
        identity_resolver=_identity("alpha", "viewer", "viewer"),
    ).test_client()

    response = client.post("/analyze", json=_payload())
    assert response.status_code == 403
    assert response.get_json() == {"error": "authorization_denied"}


def test_verified_identity_cannot_spoof_tenant_or_actor(tmp_path):
    client = create_app(
        tmp_path / "industrial.sqlite3",
        identity_resolver=_identity("alpha", "analyst", "analyst"),
    ).test_client()

    wrong_tenant = client.post(
        "/analyze",
        headers={"X-Tenant-ID": "beta", "X-Actor-ID": "analyst"},
        json=_payload(),
    )
    assert wrong_tenant.status_code == 403
    assert wrong_tenant.get_json() == {"error": "identity_scope_mismatch"}

    wrong_actor = client.post(
        "/analyze",
        headers={"X-Tenant-ID": "alpha", "X-Actor-ID": "forged-reviewer"},
        json=_payload(),
    )
    assert wrong_actor.status_code == 403
    assert wrong_actor.get_json() == {"error": "identity_scope_mismatch"}


def test_unknown_notice_deadline_fails_closed_in_api(tmp_path):
    client = create_app(
        tmp_path / "unknown-notice.sqlite3",
        identity_resolver=_identity("alpha", "analyst", "analyst"),
    ).test_client()
    payload = _payload()
    payload.pop("notice_due")

    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["notice_deadline_state"] == "UNKNOWN"
    assert NOTICE_DEADLINE_EVIDENCE in body["missing_evidence"]


def test_verified_no_notice_deadline_can_be_review_ready(tmp_path):
    client = create_app(
        tmp_path / "verified-no-notice.sqlite3",
        identity_resolver=_identity("alpha", "analyst", "analyst"),
    ).test_client()
    payload = _payload()
    payload.pop("notice_due")
    payload["notice_deadline_not_applicable"] = True

    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["notice_deadline_state"] == "VERIFIED_NONE"
    assert NOTICE_DEADLINE_EVIDENCE not in body["missing_evidence"]


def test_assisted_api_runs_role_separated_review_action_resolution(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-1", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer-1", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator-1", "operator")).test_client()

    analyzed = analyst.post("/analyze", json=_payload())
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["net_potential"] == "8500"
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["notice_deadline_state"] == "VERIFIED_DATE"
    finding_id = body["finding_id"]

    analyst_review = analyst.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "analyst must not self-approve"},
    )
    assert analyst_review.status_code == 403
    assert analyst_review.get_json() == {"error": "authorization_denied"}

    reviewed = reviewer.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "commercial basis and amount reviewed"},
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["state"] == "APPROVED"

    analyst_action = analyst.post(f"/findings/{finding_id}/action")
    assert analyst_action.status_code == 403
    assert analyst_action.get_json() == {"error": "authorization_denied"}

    actioned = operator.post(f"/findings/{finding_id}/action")
    assert actioned.status_code == 200
    assert actioned.get_json()["state"] == "ACTIONED"

    resolved = operator.post(
        f"/findings/{finding_id}/resolve",
        json={"outcome_id": "alpha:payment-1", "recovered_amount": "7000", "currency": "EUR", "evidence_ref": "bank-1"},
    )
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"


def test_admin_role_can_execute_all_web_roles(tmp_path):
    database = tmp_path / "admin.sqlite3"
    admin = create_app(database, identity_resolver=_identity("alpha", "admin-1", "admin")).test_client()

    analyzed = admin.post("/analyze", json=_payload())
    assert analyzed.status_code == 201
    finding_id = analyzed.get_json()["finding_id"]
    reviewed = admin.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "admin override"},
    )
    assert reviewed.status_code == 200
    assert admin.post(f"/findings/{finding_id}/action").status_code == 200


def test_missing_evidence_fails_closed_in_api(tmp_path):
    client = create_app(
        tmp_path / "industrial.sqlite3",
        identity_resolver=_identity("alpha", "analyst", "analyst"),
    ).test_client()
    payload = _payload()
    payload["missing_evidence"] = ["customer_authorization"]
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    assert analyzed.get_json()["state"] == "UNRESOLVED_EVIDENCE"
