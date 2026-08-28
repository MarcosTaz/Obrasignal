from flask import Flask, request

from cloud_switching.sqlite_workspace import SQLiteDecisionWorkspace
from cloud_switching.web import create_blueprint


def make_app(tmp_path):
    app = Flask(__name__)
    workspace = SQLiteDecisionWorkspace(tmp_path / "cloud-switching-web.db")
    app.register_blueprint(
        create_blueprint(
            workspace=workspace,
            resolve_tenant=lambda: request.headers.get("X-Test-Tenant"),
        )
    )
    return app


def valid_payload():
    return {
        "package_id": "case-1",
        "baseline": [
            {
                "name": "current_total",
                "annual_value": "240000",
                "certainty": "known",
                "source_id": "billing-export-1",
            }
        ],
        "migration_case": {
            "case_id": "case-1",
            "current_annual_cost": "240000",
            "status_quo_annual_cost": "300000",
            "target_annual_cost": "180000",
            "migration_engineering_cost": "30000",
            "partner_services_cost": "20000",
            "internal_labour_cost": "10000",
            "training_cost": "5000",
            "parallel_run_cost": "15000",
            "refactoring_cost": "10000",
            "risk_contingency_cost": "10000",
            "provider_credit_approved": "30000",
            "provider_credit_received": "25000",
            "partner_incentive_approved": "10000",
            "partner_incentive_received": "5000",
        },
        "incentives": [
            {
                "incentive_id": "provider",
                "program": "Provider funding",
                "status": "partially_received",
                "approved_amount": "30000",
                "received_amount": "25000",
                "approval_evidence_id": "provider-approval",
                "receipt_evidence_id": "provider-receipt",
            },
            {
                "incentive_id": "partner",
                "program": "Partner funding",
                "status": "partially_received",
                "approved_amount": "10000",
                "received_amount": "5000",
                "approval_evidence_id": "partner-approval",
                "receipt_evidence_id": "partner-receipt",
            },
        ],
    }


def test_analyze_requires_authenticated_tenant_resolver(tmp_path):
    client = make_app(tmp_path).test_client()
    response = client.post("/cloud-switching/api/analyze", json=valid_payload())
    assert response.status_code == 401


def test_assisted_web_flow_builds_saves_and_returns_decision(tmp_path):
    client = make_app(tmp_path).test_client()
    response = client.post(
        "/cloud-switching/api/analyze",
        json=valid_payload(),
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["decision_package"]["company_id"] == "tenant-a"
    assert body["decision_package"]["decision"] == "switch"
    assert body["decision_package"]["captured_incentives"] == "30000"

    loaded = client.get(
        "/cloud-switching/api/packages/case-1",
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert loaded.status_code == 200
    assert loaded.get_json()["content_hash"] == body["content_hash"]


def test_other_tenant_cannot_read_saved_package(tmp_path):
    client = make_app(tmp_path).test_client()
    assert client.post(
        "/cloud-switching/api/analyze",
        json=valid_payload(),
        headers={"X-Test-Tenant": "tenant-a"},
    ).status_code == 201

    response = client.get(
        "/cloud-switching/api/packages/case-1",
        headers={"X-Test-Tenant": "tenant-b"},
    )
    assert response.status_code == 404


def test_web_flow_fails_closed_on_incentive_ledger_mismatch(tmp_path):
    client = make_app(tmp_path).test_client()
    payload = valid_payload()
    payload["incentives"] = []
    response = client.post(
        "/cloud-switching/api/analyze",
        json=payload,
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 422
    assert "does not reconcile" in response.get_json()["error"]
