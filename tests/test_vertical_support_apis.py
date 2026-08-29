from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app


def _headers(tenant, *, role="on_call", actor="support-operator"):
    headers = {"X-Tenant-ID": tenant, "X-Actor-ID": actor}
    if role is not None:
        headers["X-Support-Role"] = role
    return headers


def _exercise_support_api(client, tenant):
    opened = client.post("/support/incidents", headers=_headers(tenant), json={
        "incident_id": "synthetic-i1", "severity": "P1", "summary": "synthetic support incident raw wording",
    })
    assert opened.status_code == 201
    assert opened.get_json()["state"] == "OPEN"
    assert opened.get_json()["owner_role"] == "on_call"
    assert "summary" not in opened.get_json()

    assert client.post(
        "/support/incidents/synthetic-i1/transition", headers=_headers(tenant), json={"target": "ACKNOWLEDGED"}
    ).get_json()["state"] == "ACKNOWLEDGED"
    assert client.post(
        "/support/incidents/synthetic-i1/transition", headers=_headers(tenant), json={"target": "INVESTIGATING"}
    ).get_json()["state"] == "INVESTIGATING"
    assert client.post(
        "/support/incidents/synthetic-i1/transition", headers=_headers(tenant), json={"target": "MITIGATED"}
    ).get_json()["state"] == "MITIGATED"

    premature = client.post(
        "/support/incidents/synthetic-i1/transition", headers=_headers(tenant),
        json={"target": "RESOLVED", "evidence_ref": "closure"},
    )
    assert premature.status_code == 422
    assert "customer update" in premature.get_json()["message"]

    updated = client.post(
        "/support/incidents/synthetic-i1/customer-update", headers=_headers(tenant),
        json={"communication_evidence_ref": "synthetic-customer-update-evidence"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["last_customer_update_at"]

    resolved = client.post(
        "/support/incidents/synthetic-i1/transition", headers=_headers(tenant),
        json={"target": "RESOLVED", "evidence_ref": "synthetic-closure-evidence"},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["state"] == "RESOLVED"
    assert resolved.get_json()["closure_evidence_present"] is True


def test_support_api_is_integrated_into_both_recovery_apps(tmp_path):
    for create_app, filename, tenant in (
        (create_contractcredit_app, "credit.sqlite3", "enterprise-a"),
        (create_aviation_app, "aviation.sqlite3", "airline-a"),
    ):
        _exercise_support_api(create_app(tmp_path / filename).test_client(), tenant)


def test_support_api_requires_trusted_support_role(tmp_path):
    client = create_contractcredit_app(tmp_path / "credit.sqlite3").test_client()
    response = client.post("/support/incidents", headers=_headers("enterprise", role=None), json={
        "incident_id": "i1", "severity": "P2", "summary": "synthetic",
    })
    assert response.status_code == 422
    assert "support role header" in response.get_json()["message"]


def test_support_api_is_tenant_scoped(tmp_path):
    client = create_aviation_app(tmp_path / "aviation.sqlite3").test_client()
    for tenant in ("tenant-a", "tenant-b"):
        opened = client.post("/support/incidents", headers=_headers(tenant), json={
            "incident_id": "same-id", "severity": "P2", "summary": f"synthetic {tenant}",
        })
        assert opened.status_code == 201
    assert client.get("/support/incidents/same-id", headers=_headers("tenant-a")).status_code == 200
    assert client.get("/support/incidents/same-id", headers=_headers("tenant-b")).status_code == 200
    assert client.get("/support/incidents/same-id", headers=_headers("tenant-c")).status_code == 404
