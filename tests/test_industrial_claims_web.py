from auth_context import RequestIdentity
from vertical_apps.industrial_claims.service import (
    CLAIM_CURRENCY_EVIDENCE,
    COMMERCIAL_BASIS_DOCUMENT,
    COST_DOCUMENT,
    EVENT_DOCUMENT,
    NOTICE_DEADLINE_EVIDENCE,
)
from vertical_apps.industrial_claims.web import create_app


def _payload():
    return {
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "cancel-1",
        "claim_family": "WIP",
        "commercial_basis_ref": "po-1",
        "cost_evidence_ref": "ledger-1",
        "currency": "EUR",
        "commercial_basis_content": "signed supply agreement and purchase order terms",
        "event_evidence_content": "documented customer cancellation event",
        "cost_evidence_content": "cost ledger supporting WIP exposure",
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
    client = create_app(tmp_path / "industrial.sqlite3", identity_resolver=_identity("alpha", "viewer", "viewer")).test_client()
    response = client.post("/analyze", json=_payload())
    assert response.status_code == 403
    assert response.get_json() == {"error": "authorization_denied"}


def test_verified_identity_cannot_spoof_tenant_or_actor(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    wrong_tenant = client.post("/analyze", headers={"X-Tenant-ID": "beta", "X-Actor-ID": "analyst"}, json=_payload())
    assert wrong_tenant.status_code == 403
    assert wrong_tenant.get_json() == {"error": "identity_scope_mismatch"}
    wrong_actor = client.post("/analyze", headers={"X-Tenant-ID": "alpha", "X-Actor-ID": "forged-reviewer"}, json=_payload())
    assert wrong_actor.status_code == 403
    assert wrong_actor.get_json() == {"error": "identity_scope_mismatch"}


def test_reference_only_sources_fail_closed_in_api(tmp_path):
    client = create_app(tmp_path / "reference-only.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload()
    payload.pop("commercial_basis_content")
    payload.pop("event_evidence_content")
    payload.pop("cost_evidence_content")
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["currency"] == "EUR"
    assert set(body["evidence_states"].values()) == {"REFERENCE_ONLY"}
    assert {COMMERCIAL_BASIS_DOCUMENT, EVENT_DOCUMENT, COST_DOCUMENT} <= set(body["missing_evidence"])


def test_missing_claim_currency_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "missing-currency.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload()
    payload.pop("currency")
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["currency"] == "UNKNOWN"
    assert CLAIM_CURRENCY_EVIDENCE in body["missing_evidence"]


def test_unknown_notice_deadline_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "unknown-notice.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload()
    payload.pop("notice_due")
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["notice_deadline_state"] == "UNKNOWN"
    assert NOTICE_DEADLINE_EVIDENCE in body["missing_evidence"]
    assert set(body["evidence_states"].values()) == {"CONTENT_HASHED"}


def test_verified_no_notice_deadline_can_be_review_ready(tmp_path):
    client = create_app(tmp_path / "verified-no-notice.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload()
    payload.pop("notice_due")
    payload["notice_deadline_not_applicable"] = True
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["currency"] == "EUR"
    assert body["notice_deadline_state"] == "VERIFIED_NONE"
    assert NOTICE_DEADLINE_EVIDENCE not in body["missing_evidence"]
    assert set(body["evidence_states"].values()) == {"CONTENT_HASHED"}


def test_assisted_api_runs_role_separated_review_action_resolution(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-1", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer-1", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator-1", "operator")).test_client()

    analyzed = analyst.post("/analyze", json=_payload())
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["net_potential"] == "8500"
    assert body["currency"] == "EUR"
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["notice_deadline_state"] == "VERIFIED_DATE"
    assert set(body["evidence_states"].values()) == {"CONTENT_HASHED"}
    finding_id = body["finding_id"]

    analyst_review = analyst.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "analyst must not self-approve"})
    assert analyst_review.status_code == 403
    assert analyst_review.get_json() == {"error": "authorization_denied"}
    reviewed = reviewer.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "commercial basis and amount reviewed"})
    assert reviewed.status_code == 200
    assert reviewed.get_json()["state"] == "APPROVED"
    analyst_action = analyst.post(f"/findings/{finding_id}/action")
    assert analyst_action.status_code == 403
    assert analyst_action.get_json() == {"error": "authorization_denied"}
    actioned = operator.post(f"/findings/{finding_id}/action")
    assert actioned.status_code == 200
    assert actioned.get_json()["state"] == "ACTIONED"

    wrong_currency = operator.post(
        f"/findings/{finding_id}/resolve",
        json={"outcome_id": "alpha:payment-usd", "recovered_amount": "7000", "currency": "USD", "evidence_ref": "bank-usd"},
    )
    assert wrong_currency.status_code == 422
    assert "currency" in wrong_currency.get_json()["message"]

    resolved = operator.post(
        f"/findings/{finding_id}/resolve",
        json={"outcome_id": "alpha:payment-1", "recovered_amount": "7000", "currency": "eur", "evidence_ref": "bank-1"},
    )
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"
    assert resolved.get_json()["currency"] == "EUR"


def test_admin_role_spans_functions_but_not_four_eyes(tmp_path):
    database = tmp_path / "admin.sqlite3"
    admin_creator = create_app(database, identity_resolver=_identity("alpha", "admin-1", "admin")).test_client()
    admin_reviewer = create_app(database, identity_resolver=_identity("alpha", "admin-2", "admin")).test_client()
    analyzed = admin_creator.post("/analyze", json=_payload())
    assert analyzed.status_code == 201
    finding_id = analyzed.get_json()["finding_id"]
    self_review = admin_creator.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "admin cannot self approve"})
    assert self_review.status_code == 422
    assert "independent" in self_review.get_json()["message"]
    reviewed = admin_reviewer.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "independent admin review"})
    assert reviewed.status_code == 200
    assert admin_creator.post(f"/findings/{finding_id}/action").status_code == 200


def test_missing_evidence_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload()
    payload["missing_evidence"] = ["customer_authorization"]
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    assert analyzed.get_json()["state"] == "UNRESOLVED_EVIDENCE"
