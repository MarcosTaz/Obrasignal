from factory_cloud.architecture_snapshot import build_architecture_snapshot


def test_architecture_snapshot_is_non_authoritative_and_complete():
    snapshot = build_architecture_snapshot()
    assert snapshot["authority"] == {
        "source": "planning_and_switchboard_metadata_only",
        "grants_repository_write": False,
        "grants_production_write": False,
        "grants_cross_app_data_access": False,
        "grants_merge": False,
    }
    assert "control" in snapshot["factories_by_layer"]
    assert "verticals" in snapshot["factories_by_layer"]
    assert "shared-platform" in snapshot["capabilities_by_layer"]
    assert "assurance-kernel" in snapshot["capabilities_by_layer"]
    promotions = {item["factory_id"]: item for item in snapshot["app_promotion_queue"]}
    assert promotions["aviation-lease-entitlement-recovery"]["state"] == "APP_REGISTERED"
    assert promotions["contractcredit"]["state"] == "APP_REGISTERED"
    assert promotions["industrial-claims"]["state"] == "APP_REGISTERED"
    assert promotions["industrial-claims"]["blocker"] == ""
    assert promotions["warrantyguard"]["state"] == "PROMOTION_BLOCKED"
