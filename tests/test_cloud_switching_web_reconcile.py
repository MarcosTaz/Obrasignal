from flask import Flask, request

from cloud_switching.sqlite_workspace import SQLiteDecisionWorkspace
from cloud_switching.web import create_blueprint


def app_and_client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(
        create_blueprint(
            workspace=SQLiteDecisionWorkspace(tmp_path / "reconcile.db"),
            resolve_tenant=lambda: request.headers.get("X-Test-Tenant"),
        )
    )
    return app.test_client()


def baseline_payload():
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
        "baseline": [{"name": "current", "annual_value": "240000", "certainty": "known", "source_id": "billing"}],
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
            {"incentive_id": "provider", "program": "provider", "status": "partially_received", "approved_amount": "30000", "received_amount": "25000", "approval_evidence_id": "a", "receipt_evidence_id": "r"},
            {"incentive_id": "partner", "program": "partner", "status": "partially_received", "approved_amount": "10000", "received_amount": "5000", "approval_evidence_id": "pa", "receipt_evidence_id": "pr"},
        ],
        "options": [
            {"option_id": "renew", "option_type": "renew", "destination": "vmware", "currency": "EUR", "annual_run_cost": "300000"},
            {"option_id": "aws", "option_type": "switch", "destination": "aws", "currency": "EUR", "annual_run_cost": "180000", "one_time_switching_cost": "100000", "received_incentives": "30000"},
        ],
    }


def reconciliation_payload(case_id="case-1"):
    evidence = {"source_id": "machine-export", "strength": "machine_verified", "independent": True, "methodology_version": "v0.1"}
    def field(forecast, actual):
        return {"forecast": str(forecast), "actual": str(actual), "evidence": evidence}
    return {
        "pre_run_cost": "240000",
        "pre_observation": {"months": 12, "workload_units": "1000000", "service_level": "gold"},
        "post_observation": {"months": 12, "workload_units": "1100000", "service_level": "gold"},
        "outcome": {
            "case_id": case_id,
            "source_platform": "vmware",
            "destination_platform": "aws",
            "workload_class": "vm",
            "migration_strategy": "rehost",
            "migration_cost": field(100000, 120000),
            "duration_days": field(180, 240),
            "annual_run_cost": field(180000, 200000),
            "downtime_minutes": field(30, 90),
            "provider_incentive": field(40000, 30000),
        },
    }


def test_reconcile_updates_same_persisted_delivery(tmp_path):
    client = app_and_client(tmp_path)
    headers = {"X-Test-Tenant": "tenant-a"}
    created = client.post("/cloud-switching/api/analyze", json=baseline_payload(), headers=headers)
    assert created.status_code == 201
    initial_hash = created.get_json()["delivery_content_hash"]

    reconciled = client.post(
        "/cloud-switching/api/packages/case-1/reconcile",
        json=reconciliation_payload(),
        headers=headers,
    )
    assert reconciled.status_code == 200
    body = reconciled.get_json()
    assert body["delivery_version"] == 2
    assert body["delivery_content_hash"] != initial_hash
    assert body["outcome"]["reconciliation"]["migration_cost_variance"] == "20000"
    assert body["outcome"]["reconciliation"]["provider_incentive_variance"] == "-10000"
    assert body["outcome"]["reconciliation"]["verified_for_benchmark"] is True

    returned = client.get("/cloud-switching/api/packages/case-1", headers=headers).get_json()
    assert returned["delivery_content_hash"] == body["delivery_content_hash"]
    assert returned["delivery"]["estate"]["decision_ready"] is True
    assert returned["delivery"]["outcome"] == body["outcome"]


def test_reconcile_refuses_wrong_case_identity(tmp_path):
    client = app_and_client(tmp_path)
    headers = {"X-Test-Tenant": "tenant-a"}
    assert client.post("/cloud-switching/api/analyze", json=baseline_payload(), headers=headers).status_code == 201
    response = client.post(
        "/cloud-switching/api/packages/case-1/reconcile",
        json=reconciliation_payload(case_id="other-case"),
        headers=headers,
    )
    assert response.status_code == 422
    assert "frozen forecast" in response.get_json()["error"]


def test_reconcile_refuses_rewritten_forecast_value(tmp_path):
    client = app_and_client(tmp_path)
    headers = {"X-Test-Tenant": "tenant-a"}
    assert client.post("/cloud-switching/api/analyze", json=baseline_payload(), headers=headers).status_code == 201
    payload = reconciliation_payload()
    payload["outcome"]["migration_cost"]["forecast"] = "50000"
    response = client.post(
        "/cloud-switching/api/packages/case-1/reconcile",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 422
    assert "does not match frozen forecast" in response.get_json()["error"]


def test_reconcile_refuses_rewritten_destination(tmp_path):
    client = app_and_client(tmp_path)
    headers = {"X-Test-Tenant": "tenant-a"}
    assert client.post("/cloud-switching/api/analyze", json=baseline_payload(), headers=headers).status_code == 201
    payload = reconciliation_payload()
    payload["outcome"]["destination_platform"] = "azure"
    response = client.post(
        "/cloud-switching/api/packages/case-1/reconcile",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 422
    assert "destination_platform" in response.get_json()["error"]


def test_other_tenant_cannot_reconcile_foreign_delivery(tmp_path):
    client = app_and_client(tmp_path)
    assert client.post("/cloud-switching/api/analyze", json=baseline_payload(), headers={"X-Test-Tenant": "tenant-a"}).status_code == 201
    response = client.post(
        "/cloud-switching/api/packages/case-1/reconcile",
        json=reconciliation_payload(),
        headers={"X-Test-Tenant": "tenant-b"},
    )
    assert response.status_code == 404
