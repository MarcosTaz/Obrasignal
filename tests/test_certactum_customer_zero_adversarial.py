from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app


def _identity(tenant: str, actor: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant,
        authenticated=True,
        subject=actor,
        claims={"sub": actor, "roles": list(roles)},
    )


def _payload():
    return {
        "customer_ref": "customer-zero",
        "program_ref": "program-zero",
        "event_ref": "change-zero",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-zero",
        "cost_evidence_ref": "ledger-zero",
        "currency": "EUR",
        "commercial_basis_content": "synthetic signed basis",
        "event_evidence_content": "synthetic directed change",
        "cost_evidence_content": "synthetic incremental ledger",
        "gross_cost": "10000",
        "notice_deadline_not_applicable": True,
    }


def test_customer_zero_cross_tenant_and_role_abuse_fails_closed(tmp_path):
    database = tmp_path / "customer-zero.sqlite3"
    analyst_a = create_app(
        database,
        identity_resolver=_identity("tenant-a", "analyst-a", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()
    reviewer_a = create_app(
        database,
        identity_resolver=_identity("tenant-a", "reviewer-a", "reviewer"),
        allow_inline_evidence_content=True,
    ).test_client()
    operator_a = create_app(
        database,
        identity_resolver=_identity("tenant-a", "operator-a", "operator"),
        allow_inline_evidence_content=True,
    ).test_client()
    analyst_b = create_app(
        database,
        identity_resolver=_identity("tenant-b", "analyst-b", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()

    created = analyst_a.post("/analyze", json=_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]

    assert analyst_b.get(f"/findings/{finding_id}").status_code == 422
    assert analyst_b.get(f"/findings/{finding_id}/proof-pack").status_code == 422
    assert analyst_a.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "self approval attempt"},
    ).status_code == 403
    assert reviewer_a.post(
        f"/findings/{finding_id}/action",
    ).status_code == 403
    assert operator_a.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "role escalation attempt"},
    ).status_code == 403

    reviewed = reviewer_a.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "independent customer-zero review"},
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["recoverability_established"] is False
    actioned = operator_a.post(f"/findings/{finding_id}/action")
    assert actioned.status_code == 200
    assert actioned.get_json()["customer_contact_performed"] is False
    assert actioned.get_json()["external_claim_submitted"] is False


def test_customer_zero_spoofed_identity_headers_are_rejected(tmp_path):
    database = tmp_path / "customer-zero-spoof.sqlite3"
    analyst = create_app(
        database,
        identity_resolver=_identity("tenant-a", "analyst-a", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()

    response = analyst.post(
        "/analyze",
        json=_payload(),
        headers={"X-Tenant-ID": "tenant-b", "X-Actor-ID": "attacker"},
    )
    assert response.status_code == 403
    assert response.get_json() == {"error": "identity_scope_mismatch"}
