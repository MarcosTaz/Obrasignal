from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier, signed_test_headers
from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app

SECRET = "s" * 32
NOW = 1_800_000_000
VERIFIER = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)


def _headers(tenant, *, role="on_call", actor="support-operator", method="POST", path="/support/incidents"):
    return signed_test_headers(
        secret=SECRET, tenant_id=tenant, actor_id=actor,
        method=method, path=path, timestamp=NOW, support_role=(role or ""),
    )


def _exercise_support_api(client, tenant):
    opened = client.post("/support/incidents", headers=_headers(tenant), json={
        "incident_id": "synthetic-i1", "severity": "P1", "summary": "synthetic support incident raw wording",
    })
    assert opened.status_code == 201
    assert opened.get_json()["state"] == "OPEN"
    assert opened.get_json()["owner_role"] == "on_call"
    assert "summary" not in opened.get_json()

    transition_path = "/support/incidents/synthetic-i1/transition"
    for target in ("ACKNOWLEDGED", "INVESTIGATING", "MITIGATED"):
        response = client.post(transition_path, headers=_headers(tenant, path=transition_path), json={"target": target})
        assert response.get_json()["state"] == target

    premature = client.post(
        transition_path, headers=_headers(tenant, path=transition_path),
        json={"target": "RESOLVED", "evidence_ref": "closure"},
    )
    assert premature.status_code == 422
    assert "customer update" in premature.get_json()["message"]

    update_path = "/support/incidents/synthetic-i1/customer-update"
    updated = client.post(
        update_path, headers=_headers(tenant, path=update_path),
        json={"communication_evidence_ref": "synthetic-customer-update-evidence"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["last_customer_update_at"]

    resolved = client.post(
        transition_path, headers=_headers(tenant, path=transition_path),
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
        client = create_app(tmp_path / filename, identity_resolver=VERIFIER.verify_request).test_client()
        _exercise_support_api(client, tenant)


def test_support_api_requires_signed_allowlisted_support_role(tmp_path):
    client = create_contractcredit_app(tmp_path / "credit.sqlite3", identity_resolver=VERIFIER.verify_request).test_client()
    missing = client.post("/support/incidents", headers=_headers("enterprise", role=None), json={
        "incident_id": "i1", "severity": "P2", "summary": "synthetic",
    })
    assert missing.status_code == 422
    assert "support role header" in missing.get_json()["message"]

    unauthorized = client.post("/support/incidents", headers=_headers("enterprise", role="billing_admin"), json={
        "incident_id": "i2", "severity": "P2", "summary": "synthetic",
    })
    assert unauthorized.status_code == 422
    assert "not authorized" in unauthorized.get_json()["message"]

    signed_as_viewer = _headers("enterprise", role="support_operator")
    signed_as_viewer["X-Support-Role"] = "support_manager"
    tampered = client.post("/support/incidents", headers=signed_as_viewer, json={
        "incident_id": "i3", "severity": "P2", "summary": "synthetic",
    })
    assert tampered.status_code == 422
    assert "signature" in tampered.get_json()["message"]


def test_support_api_is_tenant_scoped(tmp_path):
    client = create_aviation_app(tmp_path / "aviation.sqlite3", identity_resolver=VERIFIER.verify_request).test_client()
    for tenant in ("tenant-a", "tenant-b"):
        opened = client.post("/support/incidents", headers=_headers(tenant), json={
            "incident_id": "same-id", "severity": "P2", "summary": f"synthetic {tenant}",
        })
        assert opened.status_code == 201
    get_path = "/support/incidents/same-id"
    assert client.get(get_path, headers=_headers("tenant-a", method="GET", path=get_path)).status_code == 200
    assert client.get(get_path, headers=_headers("tenant-b", method="GET", path=get_path)).status_code == 200
    assert client.get(get_path, headers=_headers("tenant-c", method="GET", path=get_path)).status_code == 404
