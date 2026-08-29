from cloud_switching.sqlite_workspace import SQLiteDecisionWorkspace


def test_full_delivery_survives_process_style_reopen(tmp_path):
    path = tmp_path / "delivery-restart.db"
    first = SQLiteDecisionWorkspace(path)
    payload = {
        "estate": {
            "total_assets": 2,
            "vm_count": 2,
            "host_count": 0,
            "stale_asset_ids": [],
            "unknown_asset_ids": [],
            "missing_capacity_asset_ids": [],
            "decision_ready": True,
        },
        "decision": {"company_id": "tenant-a", "case_id": "case-1", "decision": "switch"},
        "options": {"economic_winner_id": "aws", "customer_cash_winner_id": "azure"},
        "forecast": {
            "case_id": "case-1",
            "source_platform": "vmware",
            "destination_platform": "aws",
            "workload_class": "vm",
            "migration_strategy": "rehost",
            "migration_cost": "125000",
            "duration_days": "180",
            "annual_run_cost": "180000",
            "downtime_minutes": "30",
            "incentive_total": "40000",
            "methodology_version": "v0.1",
        },
        "outcome": {
            "identity": {"case_id": "case-1"},
            "reconciliation": {"migration_cost_variance": "20000", "verified_for_benchmark": True},
        },
    }
    saved = first.save_delivery(tenant_id="tenant-a", package_id="case-1", payload=payload)

    reopened = SQLiteDecisionWorkspace(path)
    loaded = reopened.load_delivery(tenant_id="tenant-a", package_id="case-1")

    assert loaded is not None
    assert loaded.payload == payload
    assert loaded.content_hash == saved.content_hash
    assert loaded.version == saved.version
    assert loaded.payload["estate"]["decision_ready"] is True
    assert loaded.payload["forecast"]["methodology_version"] == "v0.1"
    assert loaded.payload["outcome"]["reconciliation"]["verified_for_benchmark"] is True


def test_full_delivery_restart_remains_tenant_isolated(tmp_path):
    path = tmp_path / "delivery-restart.db"
    first = SQLiteDecisionWorkspace(path)
    payload = {
        "decision": {"company_id": "tenant-a", "case_id": "case-1"},
        "estate": {"decision_ready": True},
        "options": {},
        "forecast": {},
        "outcome": None,
    }
    first.save_delivery(tenant_id="tenant-a", package_id="case-1", payload=payload)

    reopened = SQLiteDecisionWorkspace(path)
    assert reopened.load_delivery(tenant_id="tenant-b", package_id="case-1") is None
