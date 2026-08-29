import pytest

from factory_cloud.shared_contracts import SharedContractError
from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier, signed_test_headers
from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app

SECRET = "s" * 32
NOW = 1_800_000_000
VERIFIER = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)


def _client(create_app, database):
    return create_app(database, identity_resolver=VERIFIER.verify_request).test_client()


def _headers(tenant="tenant-a", actor="analyst", *, method="POST", path="/analyze"):
    return signed_test_headers(
        secret=SECRET, tenant_id=tenant, actor_id=actor,
        method=method, path=path, timestamp=NOW,
    )


def test_apps_fail_closed_at_startup_without_configured_identity_verifier(tmp_path, monkeypatch):
    monkeypatch.delenv("ASSISTED_UPSTREAM_HMAC_KEY", raising=False)
    for create_app, filename in ((create_aviation_app, "aviation.sqlite3"), (create_contractcredit_app, "credit.sqlite3")):
        with pytest.raises(SharedContractError, match="not configured"):
            create_app(tmp_path / filename)


def test_health_endpoints_are_explicitly_assisted(tmp_path):
    aviation = _client(create_aviation_app, tmp_path / "aviation.sqlite3")
    credit = _client(create_contractcredit_app, tmp_path / "credit.sqlite3")
    assert aviation.get("/health").get_json()["mode"] == "assisted"
    assert credit.get("/health").get_json()["mode"] == "assisted"


def test_assisted_web_workspaces_expose_full_action_surface_without_identity_override(tmp_path):
    aviation = _client(create_aviation_app, tmp_path / "aviation.sqlite3")
    credit = _client(create_contractcredit_app, tmp_path / "credit.sqlite3")
    for client, expected_field in ((aviation, 'name="eligible_cost"'), (credit, 'name="monthly_fee"')):
        response = client.get("/")
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert response.content_type.startswith("text/html")
        assert "assisted, pre-customer certification" in body
        assert "synthetic/shadow evidence only until PILOT_SAFE" in body
        assert expected_field in body
        assert 'id="analysis-form"' in body
        assert 'id="review-form"' in body
        assert 'id="action-form"' in body
        assert 'id="resolve-form"' in body
        assert 'aria-live="polite"' in body
        assert 'name="tenant_id"' not in body
        assert 'name="actor_id"' not in body
        assert "X-Upstream-Signature" not in body


def test_aviation_web_api_full_flow_and_tenant_isolation(tmp_path):
    client = _client(create_aviation_app, tmp_path / "aviation.sqlite3")
    response = client.post("/analyze", headers=_headers("airline", path="/analyze"), json={
        "contract_ref": "lease-1", "event_ref": "shop-1",
        "eligible_cost": "100000", "reimbursed_amount": "25000",
        "notice_due": "2026-09-30",
    })
    assert response.status_code == 201
    finding_id = response.get_json()["finding_id"]
    assert response.get_json()["potential_value"] == "75000"

    review_path = f"/findings/{finding_id}/review"
    cross = client.post(review_path, headers=_headers("other", "reviewer", path=review_path), json={"approved": True, "reason": "x"})
    assert cross.status_code == 422

    review = client.post(review_path, headers=_headers("airline", "reviewer", path=review_path), json={"approved": True, "reason": "supported evidence"})
    assert review.status_code == 200
    assert review.get_json()["state"] == "APPROVED"
    action_path = f"/findings/{finding_id}/action"
    assert client.post(action_path, headers=_headers("airline", path=action_path)).get_json()["state"] == "ACTIONED"
    resolve_path = f"/findings/{finding_id}/resolve"
    outcome = client.post(resolve_path, headers=_headers("airline", path=resolve_path), json={
        "outcome_id": "aviation-outcome-1", "recovered_amount": "75000",
        "currency": "EUR", "evidence_ref": "settlement-1",
    })
    assert outcome.status_code == 201
    assert outcome.get_json()["state"] == "RECOVERED"


def test_contractcredit_web_api_full_flow(tmp_path):
    client = _client(create_contractcredit_app, tmp_path / "credit.sqlite3")
    response = client.post("/analyze", headers=_headers("enterprise", path="/analyze"), json={
        "contract_ref": "msa-1", "incident_ref": "sev1-1",
        "monthly_fee": "50000", "credit_rate": "0.10", "notice_due": "2026-09-15",
    })
    assert response.status_code == 201
    finding_id = response.get_json()["finding_id"]
    review_path = f"/findings/{finding_id}/review"
    bad_review = client.post(review_path, headers=_headers("enterprise", "reviewer", path=review_path), json={"approved": "yes", "reason": "bad type"})
    assert bad_review.status_code == 422
    review = client.post(review_path, headers=_headers("enterprise", "reviewer", path=review_path), json={"approved": True, "reason": "supported evidence"})
    assert review.get_json()["state"] == "APPROVED"
    action_path = f"/findings/{finding_id}/action"
    assert client.post(action_path, headers=_headers("enterprise", path=action_path)).get_json()["state"] == "ACTIONED"
    resolve_path = f"/findings/{finding_id}/resolve"
    outcome = client.post(resolve_path, headers=_headers("enterprise", path=resolve_path), json={
        "outcome_id": "credit-outcome-1", "recovered_amount": "5000",
        "currency": "EUR", "evidence_ref": "credit-note-1",
    })
    assert outcome.status_code == 201
    assert outcome.get_json()["state"] == "RECOVERED"


def test_unsigned_or_path_replayed_identity_headers_are_rejected(tmp_path):
    client = _client(create_contractcredit_app, tmp_path / "credit.sqlite3")
    unsigned = client.post("/analyze", headers={"X-Tenant-ID": "enterprise", "X-Actor-ID": "analyst"}, json={})
    assert unsigned.status_code == 422
    assert "timestamp" in unsigned.get_json()["message"] or "signature" in unsigned.get_json()["message"]

    headers = _headers("enterprise", path="/analyze")
    replay = client.post("/shadow/analyze", headers=headers, json={})
    assert replay.status_code == 422
    assert "signature" in replay.get_json()["message"]
