import json

from factory_cloud.pilot_safe_matrix import assess, assess_manifest, portfolio_matrix, required_evidence


def test_missing_evidence_blocks_pilot_safe():
    result = assess("contractcredit", set())
    assert result["classification"] == "NOT_PILOT_SAFE"
    assert result["gates"]["PS1"] == "BLOCKED"
    assert "web_complete" in result["missing_evidence"]
    assert "support_continuity" in result["missing_evidence"]


def test_all_required_pre_customer_evidence_can_reach_pilot_safe():
    result = assess("contractcredit", required_evidence())
    assert result["classification"] == "PILOT_SAFE"
    assert set(result["gates"].values()) == {"PASS"}


def test_forbidden_real_customer_token_never_helps_certification():
    evidence = required_evidence() | {"real_customer"}
    result = assess("contractcredit", evidence)
    assert result["classification"] == "NOT_PILOT_SAFE"
    assert result["forbidden_evidence_seen"] == ["real_customer"]


def test_contractcredit_manifest_preserves_known_gaps():
    result = assess_manifest("factory_cloud/pilot_safe_evidence/contractcredit.json")
    assert result["classification"] == "NOT_PILOT_SAFE"
    assert result["gates"]["PS2"] == "BLOCKED"
    assert "web_complete" in result["missing_evidence"]
    assert "support_continuity" in result["missing_evidence"]
    assert "shadow_validation" in result["missing_evidence"]
    assert result["exact_source_bound"] is True


def test_aviation_manifest_preserves_known_gaps():
    result = assess_manifest("factory_cloud/pilot_safe_evidence/aviation-lease-entitlement-recovery.json")
    assert result["classification"] == "NOT_PILOT_SAFE"
    assert result["gates"]["PS3"] == "PASS"
    assert result["gates"]["PS4"] == "BLOCKED"
    assert "adversarial" in result["missing_evidence"]
    assert result["exact_source_bound"] is True


def test_stale_manifest_exact_source_cannot_earn_ps9(tmp_path):
    declared = "a" * 40
    registered = "b" * 40
    manifest = tmp_path / "manifest.json"
    apps = tmp_path / "apps.json"
    manifest.write_text(json.dumps({
        "factory_id": "contractcredit",
        "exact_source_head": declared,
        "evidence": {
            "exact_source_head": {"status": "PASS", "refs": ["apps.json"]},
            "source_registered": {"status": "PASS", "refs": ["apps.json"]},
        },
    }), encoding="utf-8")
    apps.write_text(json.dumps({
        "applications": [{
            "app_id": "contractcredit",
            "execution_source": {"verified": True, "head": registered},
        }]
    }), encoding="utf-8")
    result = assess_manifest(manifest, apps_path=apps)
    assert result["exact_source_bound"] is False
    assert result["registered_source_head"] == registered
    assert "exact_source_head" in result["missing_evidence"]
    assert result["gates"]["PS9"] == "BLOCKED"


def test_verified_execution_head_binds_exact_source_evidence(tmp_path):
    head = "c" * 40
    manifest = tmp_path / "manifest.json"
    apps = tmp_path / "apps.json"
    manifest.write_text(json.dumps({
        "factory_id": "contractcredit",
        "exact_source_head": head,
        "evidence": {
            "exact_source_head": {"status": "PASS", "refs": ["apps.json"]},
            "source_registered": {"status": "PASS", "refs": ["apps.json"]},
        },
    }), encoding="utf-8")
    apps.write_text(json.dumps({
        "applications": [{
            "app_id": "contractcredit",
            "execution_source": {"verified": True, "head": head},
        }]
    }), encoding="utf-8")
    result = assess_manifest(manifest, apps_path=apps)
    assert result["exact_source_bound"] is True
    assert result["registered_source_head"] == head
    assert "exact_source_head" not in result["missing_evidence"]


def test_portfolio_matrix_covers_registered_and_transitional_factories_fail_closed():
    matrix = portfolio_matrix()
    by_id = {row["factory_id"]: row for row in matrix}
    for factory_id in (
        "factory-cloud",
        "obrasignal",
        "contractcredit",
        "aviation-lease-entitlement-recovery",
        "guaranteerelease",
        "debtrecover",
        "royaltyrecover",
        "govmargin",
        "gridrecover",
        "dealrecover",
    ):
        assert factory_id in by_id
    assert all(row["classification"] == "NOT_PILOT_SAFE" for row in matrix)
    assert by_id["contractcredit"]["gates"]["PS3"] == "PASS"
    assert by_id["contractcredit"]["gates"]["PS2"] == "BLOCKED"
    assert by_id["dealrecover"]["source_status"] == "unregistered"
    assert "source_registered" in by_id["dealrecover"]["missing_evidence"]
