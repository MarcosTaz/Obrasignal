from auth_context import RequestIdentity
from vertical_apps.industrial_claims.service import (
    CLAIM_CURRENCY_EVIDENCE,
    COMMERCIAL_BASIS_DOCUMENT,
    COST_DOCUMENT,
    EVENT_DOCUMENT,
    NOTICE_DEADLINE_EVIDENCE,
)
from vertical_apps.industrial_claims.web import create_app as _create_app


def create_app(*args, **kwargs):
    """Existing web suite exercises the explicit synthetic/local inline-content mode."""
    kwargs.setdefault("allow_inline_evidence_content", True)
    return _create_app(*args, **kwargs)


def _payload():
    return {
        "customer_ref": "oem-1", "program_ref": "program-1", "event_ref": "cancel-1", "claim_family": "WIP",
        "commercial_basis_ref": "po-1", "cost_evidence_ref": "ledger-1", "currency": "EUR",
        "commercial_basis_content": "signed supply agreement and purchase order terms",
        "event_evidence_content": "documented customer cancellation event",
        "cost_evidence_content": "cost ledger supporting WIP exposure",
        "gross_cost": "10000", "avoided_cost": "1000", "prior_payment": "500", "notice_due": "2026-09-30",
    }


def _outcome_payload(**overrides):
    payload = {
        "outcome_id": "payment-1",
        "recovered_amount": "7000",
        "currency": "EUR",
        "evidence_ref": "bank-1",
        "evidence_content": "bank statement documents 7000 EUR receipt",
        "final_cumulative": True,
    }
    payload.update(overrides)
    return payload


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(account_id=tenant_id, authenticated=True, subject=actor_id, claims={"sub": actor_id, "roles": list(roles)})


def test_analyze_rejects_unverified_raw_identity_headers(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3").test_client()
    response = client.post("/analyze", headers={"X-Tenant-ID": "alpha", "X-Actor-ID": "analyst"}, json=_payload())
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
    for key in ("commercial_basis_content", "event_evidence_content", "cost_evidence_content"):
        payload.pop(key)
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["currency"] == "EUR"
    assert set(body["evidence_states"].values()) == {"REFERENCE_ONLY"}
    assert {COMMERCIAL_BASIS_DOCUMENT, EVENT_DOCUMENT, COST_DOCUMENT} <= set(body["missing_evidence"])


def test_missing_claim_currency_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "missing-currency.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload(); payload.pop("currency")
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["currency"] == "UNKNOWN"
    assert CLAIM_CURRENCY_EVIDENCE in body["missing_evidence"]


def test_unknown_notice_deadline_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "unknown-notice.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload(); payload.pop("notice_due")
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert body["notice_deadline_state"] == "UNKNOWN"
    assert NOTICE_DEADLINE_EVIDENCE in body["missing_evidence"]
    assert set(body["evidence_states"].values()) == {"CONTENT_HASHED"}


def test_declared_no_notice_deadline_can_be_review_ready_without_claiming_verification(tmp_path):
    client = create_app(tmp_path / "declared-no-notice.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload(); payload.pop("notice_due"); payload["notice_deadline_not_applicable"] = True
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["currency"] == "EUR"
    assert body["notice_deadline_state"] == "DECLARED_NONE_FOR_REVIEW"
    assert NOTICE_DEADLINE_EVIDENCE not in body["missing_evidence"]


def test_non_object_json_bodies_fail_closed_without_internal_server_error(tmp_path):
    database = tmp_path / "non-object-json.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator", "operator")).test_client()

    analyze = analyst.post("/analyze", json=[])
    assert analyze.status_code == 422
    assert analyze.get_json()["message"] == "JSON body must be an object"

    created = analyst.post("/analyze", json=_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]

    review = reviewer.post(f"/findings/{finding_id}/review", json=[True])
    assert review.status_code == 422
    assert review.get_json()["message"] == "JSON body must be an object"

    resolve = operator.post(f"/findings/{finding_id}/resolve", json="not-an-object")
    assert resolve.status_code == 422
    assert resolve.get_json()["message"] == "JSON body must be an object"


def test_resolution_requires_explicit_final_cumulative_confirmation_before_persistence(tmp_path):
    database = tmp_path / "final-cumulative.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator", "operator")).test_client()

    created = analyst.post("/analyze", json=_payload())
    finding_id = created.get_json()["finding_id"]
    assert reviewer.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "internal workflow review"}).status_code == 200
    assert operator.post(f"/findings/{finding_id}/action").status_code == 200

    no_confirmation = _outcome_payload()
    no_confirmation.pop("final_cumulative")
    denied = operator.post(f"/findings/{finding_id}/resolve", json=no_confirmation)
    assert denied.status_code == 422
    assert "final_cumulative must be true" in denied.get_json()["message"]

    false_confirmation = operator.post(
        f"/findings/{finding_id}/resolve",
        json=_outcome_payload(final_cumulative=False),
    )
    assert false_confirmation.status_code == 422
    assert "final_cumulative must be true" in false_confirmation.get_json()["message"]

    accepted = operator.post(f"/findings/{finding_id}/resolve", json=_outcome_payload())
    assert accepted.status_code == 201
    body = accepted.get_json()
    assert body["final_cumulative"] is True
    assert body["finding_closed_by_outcome"] is True
    assert body["state"] == "RECOVERED"


def test_assisted_api_runs_role_separated_review_action_resolution(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("alpha", "analyst-1", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("alpha", "reviewer-1", "reviewer")).test_client()
    operator = create_app(database, identity_resolver=_identity("alpha", "operator-1", "operator")).test_client()

    analyzed = analyst.post("/analyze", json=_payload())
    body = analyzed.get_json()
    assert analyzed.status_code == 201
    assert body["net_potential"] == "8500"
    assert body["currency"] == "EUR"
    assert body["state"] == "READY_FOR_REVIEW"
    assert body["notice_deadline_state"] == "DECLARED_DATE_FOR_REVIEW"
    finding_id = body["finding_id"]

    detail = analyst.get(f"/findings/{finding_id}")
    assert detail.status_code == 200
    assert detail.get_json()["review_contract"] == {
        "approval_scope": "INTERNAL_WORKFLOW_APPROVAL",
        "approval_establishes_recoverability": False,
        "approval_is_legal_conclusion": False,
        "approval_authorizes_customer_contact": False,
        "approval_authorizes_external_claim_submission": False,
    }

    analyst_review = analyst.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "analyst must not self-approve"})
    assert analyst_review.status_code == 403
    reviewed = reviewer.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "commercial basis and amount reviewed for internal workflow"})
    assert reviewed.status_code == 200
    reviewed_body = reviewed.get_json()
    assert reviewed_body["state"] == "APPROVED"
    assert reviewed_body["review_scope"] == "INTERNAL_WORKFLOW_APPROVAL"
    assert reviewed_body["recoverability_established"] is False
    assert reviewed_body["legal_conclusion"] is None
    assert reviewed_body["customer_contact_authorized"] is False
    assert reviewed_body["external_claim_submission_authorized"] is False

    assert analyst.post(f"/findings/{finding_id}/action").status_code == 403
    actioned = operator.post(f"/findings/{finding_id}/action")
    assert actioned.status_code == 200
    actioned_body = actioned.get_json()
    assert actioned_body["state"] == "ACTIONED"
    assert actioned_body["internal_workflow_only"] is True
    assert actioned_body["customer_contact_performed"] is False
    assert actioned_body["external_claim_submitted"] is False

    missing_proof = operator.post(
        f"/findings/{finding_id}/resolve",
        json=_outcome_payload(outcome_id="no-proof", evidence_ref="bank-ref-only", evidence_content=""),
    )
    assert missing_proof.status_code == 422
    assert "evidence content" in missing_proof.get_json()["message"]

    wrong_currency = operator.post(
        f"/findings/{finding_id}/resolve",
        json=_outcome_payload(outcome_id="payment-usd", currency="USD", evidence_ref="bank-usd", evidence_content="USD settlement proof"),
    )
    assert wrong_currency.status_code == 422
    assert "currency" in wrong_currency.get_json()["message"]

    resolved = operator.post(f"/findings/{finding_id}/resolve", json=_outcome_payload(currency="eur"))
    assert resolved.status_code == 201
    resolved_body = resolved.get_json()
    assert resolved_body["state"] == "RECOVERED"
    assert resolved_body["currency"] == "EUR"
    assert resolved_body["evidence_ref"].endswith(":outcome-evidence")
    assert resolved_body["final_cumulative"] is True
    assert resolved_body["finding_closed_by_outcome"] is True


def test_admin_role_spans_functions_but_not_four_eyes(tmp_path):
    database = tmp_path / "admin.sqlite3"
    admin_creator = create_app(database, identity_resolver=_identity("alpha", "admin-1", "admin")).test_client()
    admin_reviewer = create_app(database, identity_resolver=_identity("alpha", "admin-2", "admin")).test_client()
    analyzed = admin_creator.post("/analyze", json=_payload())
    finding_id = analyzed.get_json()["finding_id"]
    self_review = admin_creator.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "admin cannot self approve"})
    assert self_review.status_code == 422
    assert "independent" in self_review.get_json()["message"]
    reviewed = admin_reviewer.post(f"/findings/{finding_id}/review", json={"approved": True, "reason": "independent admin review"})
    assert reviewed.status_code == 200
    assert admin_creator.post(f"/findings/{finding_id}/action").status_code == 200


def test_missing_evidence_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    payload = _payload(); payload["missing_evidence"] = ["customer_authorization"]
    analyzed = client.post("/analyze", json=payload)
    assert analyzed.status_code == 201
    assert analyzed.get_json()["state"] == "UNRESOLVED_EVIDENCE"
