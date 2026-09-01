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
        "estate": {
            "as_of": "2026-08-29T00:00:00Z",
            "stale_after_days": 30,
            "assets": [
                {
                    "asset_id": "vm-1",
                    "asset_type": "vm",
                    "cpu_cores": 8,
                    "memory_gib": 32,
                    "storage_gib": 500,
                    "last_seen_at": "2026-08-28T23:00:00Z",
                    "certainty": "known",
                    "source_id": "vcenter-export-1",
                }
            ],
        },
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
        "forecast": {
            "case_id": "case-1",
            "source_platform": "vmware",
            "destination_platform": "aws",
            "workload_class": "vm",
            "migration_strategy": "rehost",
            "migration_cost": "100000",
            "duration_days": "180",
            "annual_run_cost": "180000",
            "downtime_minutes": "30",
            "incentive_total": "40000",
            "methodology_version": "v0.1",
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
        "options": [
            {
                "option_id": "renew",
                "option_type": "renew",
                "destination": "vmware",
                "currency": "EUR",
                "annual_run_cost": "300000",
            },
            {
                "option_id": "aws",
                "option_type": "switch",
                "destination": "aws",
                "currency": "EUR",
                "annual_run_cost": "180000",
                "one_time_switching_cost": "100000",
                "received_incentives": "30000",
            },
        ],
    }


def test_analyze_requires_authenticated_tenant_resolver(tmp_path):
    client = make_app(tmp_path).test_client()
    response = client.post("/cloud-switching/api/analyze", json=valid_payload())
    assert response.status_code == 401


def test_assisted_web_flow_builds_saves_returns_decision_options_forecast_and_estate(tmp_path):
    client = make_app(tmp_path).test_client()
    response = client.post(
        "/cloud-switching/api/analyze",
        json=valid_payload(),
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["estate_assessment"]["decision_ready"] is True
    assert body["estate_assessment"]["vm_count"] == 1
    assert body["decision_package"]["company_id"] == "tenant-a"
    assert body["decision_package"]["decision"] == "switch"
    assert body["decision_package"]["captured_incentives"] == "30000"
    assert body["option_comparison"]["economic_winner_id"] == "aws"
    assert body["option_comparison"]["customer_cash_winner_id"] == "aws"
    assert body["frozen_forecast"]["migration_cost"] == "100000"
    assert body["frozen_forecast"]["incentive_total"] == "40000"
    assert body["delivery_content_hash"]

    loaded = client.get(
        "/cloud-switching/api/packages/case-1",
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert loaded.status_code == 200
    loaded_body = loaded.get_json()
    assert loaded_body["delivery_content_hash"] == body["delivery_content_hash"]
    assert loaded_body["delivery"]["estate"] == body["estate_assessment"]
    assert loaded_body["delivery"]["decision"] == body["decision_package"]
    assert loaded_body["delivery"]["options"] == body["option_comparison"]
    assert loaded_body["delivery"]["forecast"] == body["frozen_forecast"]


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


def test_web_flow_requires_real_alternative_comparison(tmp_path):
    client = make_app(tmp_path).test_client()
    payload = valid_payload()
    payload["options"] = payload["options"][:1]
    response = client.post(
        "/cloud-switching/api/analyze",
        json=payload,
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 422
    assert "at least two" in response.get_json()["error"]


def test_forecast_financials_must_reconcile_before_being_frozen(tmp_path):
    client = make_app(tmp_path).test_client()
    payload = valid_payload()
    payload["forecast"]["migration_cost"] = "99999"
    response = client.post(
        "/cloud-switching/api/analyze",
        json=payload,
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 422
    assert "gross switching cost" in response.get_json()["error"]


def test_analyze_refuses_missing_estate(tmp_path):
    client = make_app(tmp_path).test_client()
    payload = valid_payload()
    payload.pop("estate")
    response = client.post(
        "/cloud-switching/api/analyze",
        json=payload,
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 422
    assert "estate object is required" in response.get_json()["error"]


def test_analyze_refuses_stale_estate(tmp_path):
    client = make_app(tmp_path).test_client()
    payload = valid_payload()
    payload["estate"]["assets"][0]["last_seen_at"] = "2026-01-01T00:00:00Z"
    response = client.post(
        "/cloud-switching/api/analyze",
        json=payload,
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 422
    assert "estate is not decision-ready" in response.get_json()["error"]


def test_analyze_refuses_unknown_estate_asset(tmp_path):
    client = make_app(tmp_path).test_client()
    payload = valid_payload()
    payload["estate"]["assets"][0]["certainty"] = "unknown"
    payload["estate"]["assets"][0]["source_id"] = None
    response = client.post(
        "/cloud-switching/api/analyze",
        json=payload,
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert response.status_code == 422
    assert "estate is not decision-ready" in response.get_json()["error"]
