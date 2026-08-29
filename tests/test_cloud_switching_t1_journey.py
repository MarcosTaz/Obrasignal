from flask import Flask, request

from cloud_switching.sqlite_workspace import SQLiteDecisionWorkspace
from cloud_switching.web import create_blueprint


def make_client(db_path):
    app = Flask(__name__)
    app.register_blueprint(
        create_blueprint(
            workspace=SQLiteDecisionWorkspace(db_path),
            resolve_tenant=lambda: request.headers.get("X-Test-Tenant"),
        )
    )
    return app.test_client()


def pre_migration_payload():
    return {
        "package_id": "pilot-1",
        "estate": {
            "as_of": "2026-08-29T00:00:00Z",
            "assets": [
                {
                    "asset_id": "vm-001",
                    "asset_type": "vm",
                    "cpu_cores": 8,
                    "memory_gib": 32,
                    "storage_gib": 500,
                    "last_seen_at": "2026-08-28T23:00:00Z",
                    "certainty": "known",
                    "source_id": "vcenter-export",
                },
                {
                    "asset_id": "vm-002",
                    "asset_type": "vm",
                    "cpu_cores": 16,
                    "memory_gib": 64,
                    "storage_gib": 1000,
                    "last_seen_at": "2026-08-28T23:00:00Z",
                    "certainty": "known",
                    "source_id": "vcenter-export",
                },
            ],
        },
        "baseline": [
            {
                "name": "current_total",
                "annual_value": "240000",
                "certainty": "known",
                "source_id": "invoice-export",
            }
        ],
        "migration_case": {
            "case_id": "pilot-1",
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
            "data_movement_cost": "12000",
            "decommissioning_cost": "8000",
            "backup_dr_transition_cost": "7000",
            "security_transition_cost": "6000",
            "support_transition_cost": "5000",
            "provider_credit_approved": "30000",
            "provider_credit_received": "25000",
            "partner_incentive_approved": "10000",
            "partner_incentive_received": "5000",
        },
        "forecast": {
            "case_id": "pilot-1",
            "source_platform": "vmware",
            "destination_platform": "aws",
            "workload_class": "vm",
            "migration_strategy": "rehost",
            "migration_cost": "138000",
            "duration_days": "180",
            "annual_run_cost": "180000",
            "downtime_minutes": "30",
            "incentive_total": "40000",
            "methodology_version": "v0.1",
        },
        "incentives": [
            {
                "incentive_id": "provider",
                "program": "provider",
                "status": "partially_received",
                "approved_amount": "30000",
                "received_amount": "25000",
                "approval_evidence_id": "provider-approval",
                "receipt_evidence_id": "provider-receipt",
            },
            {
                "incentive_id": "partner",
                "program": "partner",
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
                "one_time_switching_cost": "138000",
                "received_incentives": "30000",
            },
        ],
    }


def actual_payload():
    evidence = {
        "source_id": "machine-export",
        "strength": "machine_verified",
        "independent": True,
        "methodology_version": "v0.1",
    }

    def measured(forecast, actual):
        return {"forecast": str(forecast), "actual": str(actual), "evidence": evidence}

    return {
        "pre_run_cost": "240000",
        "pre_observation": {"months": 12, "workload_units": "1000000", "service_level": "gold"},
        "post_observation": {"months": 12, "workload_units": "1000000", "service_level": "gold"},
        "outcome": {
            "case_id": "pilot-1",
            "source_platform": "vmware",
            "destination_platform": "aws",
            "workload_class": "vm",
            "migration_strategy": "rehost",
            "migration_cost": measured(138000, 150000),
            "duration_days": measured(180, 210),
            "annual_run_cost": measured(180000, 195000),
            "downtime_minutes": measured(30, 45),
            "provider_incentive": measured(40000, 30000),
        },
    }


def test_complete_t1_assisted_journey_survives_restart_and_reconciles(tmp_path):
    db_path = tmp_path / "pilot.db"
    headers = {"X-Test-Tenant": "tenant-a"}

    first_client = make_client(db_path)
    created = first_client.post(
        "/cloud-switching/api/analyze",
        json=pre_migration_payload(),
        headers=headers,
    )
    assert created.status_code == 201
    created_body = created.get_json()
    assert created_body["estate_assessment"]["decision_ready"] is True
    assert created_body["estate_assessment"]["vm_count"] == 2
    assert created_body["frozen_forecast"]["migration_cost"] == "138000"
    first_hash = created_body["delivery_content_hash"]

    # Simulate a process restart by constructing a new Flask app/workspace on the same DB.
    restarted_client = make_client(db_path)
    returned = restarted_client.get(
        "/cloud-switching/api/packages/pilot-1",
        headers=headers,
    )
    assert returned.status_code == 200
    returned_body = returned.get_json()
    assert returned_body["delivery_content_hash"] == first_hash
    assert returned_body["delivery"]["estate"]["decision_ready"] is True
    assert returned_body["delivery"]["forecast"]["migration_cost"] == "138000"

    reconciled = restarted_client.post(
        "/cloud-switching/api/packages/pilot-1/reconcile",
        json=actual_payload(),
        headers=headers,
    )
    assert reconciled.status_code == 200
    reconciled_body = reconciled.get_json()
    assert reconciled_body["delivery_content_hash"] != first_hash
    assert reconciled_body["outcome"]["reconciliation"]["migration_cost_variance"] == "12000"
    assert reconciled_body["outcome"]["reconciliation"]["annual_run_cost_variance"] == "15000"
    assert reconciled_body["outcome"]["reconciliation"]["verified_for_benchmark"] is True

    final = restarted_client.get(
        "/cloud-switching/api/packages/pilot-1",
        headers=headers,
    ).get_json()["delivery"]
    assert final["forecast"]["migration_cost"] == "138000"
    assert final["outcome"]["reconciliation"]["migration_cost_variance"] == "12000"
