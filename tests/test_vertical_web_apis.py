from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app


def _headers(tenant="tenant-a", actor="analyst"):
    return {"X-Tenant-ID": tenant, "X-Actor-ID": actor}


def test_health_endpoints_are_explicitly_assisted(tmp_path):
    aviation = create_aviation_app(tmp_path / "aviation.sqlite3").test_client()
    credit = create_contractcredit_app(tmp_path / "credit.sqlite3").test_client()
    assert aviation.get("/health").get_json()["mode"] == "assisted"
    assert credit.get("/health").get_json()["mode"] == "assisted"


def test_aviation_web_api_full_flow_and_tenant_isolation(tmp_path):
    client = create_aviation_app(tmp_path / "aviation.sqlite3").test_client()
    response = client.post("/analyze", headers=_headers("airline"), json={
        "contract_ref": "lease-1", "event_ref": "shop-1",
        "eligible_cost": "100000", "reimbursed_amount": "25000",
        "notice_due": "2026-09-30",
    })
    assert response.status_code == 201
    finding_id = response.get_json()["finding_id"]
    assert response.get_json()["potential_value"] == "75000"

    cross = client.post(f"/findings/{finding_id}/review", headers=_headers("other", "reviewer"), json={"approved": True, "reason": "x"})
    assert cross.status_code == 422

    review = client.post(f"/findings/{finding_id}/review", headers=_headers("airline", "reviewer"), json={"approved": True, "reason": "supported evidence"})
    assert review.status_code == 200
    assert review.get_json()["state"] == "APPROVED"
    assert client.post(f"/findings/{finding_id}/action", headers=_headers("airline")).get_json()["state"] == "ACTIONED"
    outcome = client.post(f"/findings/{finding_id}/resolve", headers=_headers("airline"), json={
        "outcome_id": "aviation-outcome-1", "recovered_amount": "75000",
        "currency": "EUR", "evidence_ref": "settlement-1",
    })
    assert outcome.status_code == 201
    assert outcome.get_json()["state"] == "RECOVERED"


def test_contractcredit_web_api_full_flow(tmp_path):
    client = create_contractcredit_app(tmp_path / "credit.sqlite3").test_client()
    response = client.post("/analyze", headers=_headers("enterprise"), json={
        "contract_ref": "msa-1", "incident_ref": "sev1-1",
        "monthly_fee": "50000", "credit_rate": "0.10", "notice_due": "2026-09-15",
    })
    assert response.status_code == 201
    finding_id = response.get_json()["finding_id"]
    bad_review = client.post(f"/findings/{finding_id}/review", headers=_headers("enterprise", "reviewer"), json={"approved": "yes", "reason": "bad type"})
    assert bad_review.status_code == 422
    review = client.post(f"/findings/{finding_id}/review", headers=_headers("enterprise", "reviewer"), json={"approved": True, "reason": "supported evidence"})
    assert review.get_json()["state"] == "APPROVED"
    assert client.post(f"/findings/{finding_id}/action", headers=_headers("enterprise")).get_json()["state"] == "ACTIONED"
    outcome = client.post(f"/findings/{finding_id}/resolve", headers=_headers("enterprise"), json={
        "outcome_id": "credit-outcome-1", "recovered_amount": "5000",
        "currency": "EUR", "evidence_ref": "credit-note-1",
    })
    assert outcome.status_code == 201
    assert outcome.get_json()["state"] == "RECOVERED"


def test_web_apis_require_trusted_upstream_identity_headers(tmp_path):
    aviation = create_aviation_app(tmp_path / "aviation.sqlite3").test_client()
    credit = create_contractcredit_app(tmp_path / "credit.sqlite3").test_client()
    aviation_response = aviation.post("/analyze", json={})
    credit_response = credit.post("/analyze", json={})
    assert aviation_response.status_code == 422
    assert credit_response.status_code == 422
    assert "identity headers" in aviation_response.get_json()["message"]
    assert "identity headers" in credit_response.get_json()["message"]
