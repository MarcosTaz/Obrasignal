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


def test_analyze_requires_trusted_upstream_identity(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3").test_client()
    response = client.post("/analyze", json=_payload())
    assert response.status_code == 422


def test_assisted_api_runs_full_review_action_resolution(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3").test_client()
    headers = {"X-Tenant-ID": "alpha", "X-Actor-ID": "analyst"}
    analyzed = client.post("/analyze", headers=headers, json=_payload())
    assert analyzed.status_code == 201
    body = analyzed.get_json()
    assert body["net_potential"] == "8500"
    assert body["state"] == "READY_FOR_REVIEW"
    finding_id = body["finding_id"]

    reviewed = client.post(
        f"/findings/{finding_id}/review",
        headers={"X-Tenant-ID": "alpha", "X-Actor-ID": "reviewer"},
        json={"approved": True, "reason": "commercial basis and amount reviewed"},
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["state"] == "APPROVED"

    actioned = client.post(f"/findings/{finding_id}/action", headers=headers)
    assert actioned.status_code == 200
    assert actioned.get_json()["state"] == "ACTIONED"

    resolved = client.post(
        f"/findings/{finding_id}/resolve",
        headers=headers,
        json={"outcome_id": "alpha:payment-1", "recovered_amount": "7000", "currency": "EUR", "evidence_ref": "bank-1"},
    )
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"


def test_missing_evidence_fails_closed_in_api(tmp_path):
    client = create_app(tmp_path / "industrial.sqlite3").test_client()
    headers = {"X-Tenant-ID": "alpha", "X-Actor-ID": "analyst"}
    payload = _payload()
    payload["missing_evidence"] = ["customer_authorization"]
    analyzed = client.post("/analyze", headers=headers, json=payload)
    assert analyzed.status_code == 201
    assert analyzed.get_json()["state"] == "UNRESOLVED_EVIDENCE"
