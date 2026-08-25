import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "acceptance" / "integration_manifest.json"
VALIDATION = ROOT / "acceptance" / "validation_20260825.json"

MATRIX_STATES = {"PASS", "FAIL", "GATED", "NOT_IMPLEMENTED", "NOT_APPLICABLE"}
COMPLETENESS_STATES = {"IMPLEMENTED", "ACCEPTED", "INTEGRATION_BLOCKED", "NOT_IMPLEMENTED", "FUTURE"}
CURRENT_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest():
    return _load(MANIFEST)


def test_acceptance_manifest_is_bound_to_current_main_and_no_merge_policy():
    manifest = _manifest()
    assert manifest["baseline"]["head_sha"] == CURRENT_MAIN
    assert manifest["baseline"]["acceptance_scope"] == "CURRENT_MAIN_PLUS_EXPLICITLY_NAMED_BRANCH_CANDIDATES"
    assert manifest["baseline"]["automatic_merge"] is False
    assert manifest["baseline"]["production_mutation"] is False
    assert manifest["baseline"]["master_queue_mutation"] is False


def test_auth_current_main_has_exact_deployed_pass_without_implying_full_product_acceptance():
    manifest = _manifest()
    auth = manifest["cross_cutting_capabilities"]["AUTH"]
    assert auth["implementation"] == "IMPLEMENTED"
    assert auth["main_sha"] == CURRENT_MAIN
    assert auth["domain_api_quality"] == "PASS"
    assert auth["deployed_acceptance"] == "PASS"
    assert manifest["main_change_observed_during_lab"]["post_merge_production_smoke"] == "PASS"
    assert manifest["main_change_observed_during_lab"]["post_merge_authenticated_e2e"] == "PASS"


def test_product_completeness_uses_only_contract_states():
    manifest = _manifest()
    expected = {"DISCOVER","SAVE","COMPARE","REQUIREMENTS","DOCUMENTS","READINESS","EVIDENCE","MILESTONES","ECONOMICS","MOBILIZATION","BANGS","DECISION","WORKSPACE","OUTCOME","BUYER","LIFECYCLE"}
    assert set(manifest["product_completeness"]) == expected
    for capability, record in manifest["product_completeness"].items():
        assert record["implementation"] in COMPLETENESS_STATES, capability
        assert record["acceptance"] in MATRIX_STATES, capability


def test_matrix_never_uses_unapproved_success_vocabulary():
    manifest = _manifest()
    assert manifest["acceptance_matrix_scope"] == "CURRENT_MAIN"
    for row in manifest["acceptance_matrix"]:
        for dimension in ("domain","combination","api","tenant","system","live"):
            assert row[dimension] in MATRIX_STATES, (row["journey"], dimension, row[dimension])


def test_release_subset_promotes_only_repaired_exact_current_main_truth():
    subset = {item["id"]: item for item in _manifest()["release_golden_subset"]}
    assert set(subset) == {"RELEASE_GOLDEN_01","RELEASE_GOLDEN_02","RELEASE_GOLDEN_03","RELEASE_GOLDEN_04","RELEASE_GOLDEN_05","RELEASE_GOLDEN_06"}
    assert subset["RELEASE_GOLDEN_01"]["status"] == "PASS"
    assert subset["RELEASE_GOLDEN_03"]["status"] == "PASS"
    assert subset["RELEASE_GOLDEN_04"]["status"] == "PASS"
    assert subset["RELEASE_GOLDEN_02"]["status"] != "PASS"
    assert subset["RELEASE_GOLDEN_06"]["status"] != "PASS"


def test_every_current_defect_has_owner_fix_and_retest_contract():
    for defect in _manifest()["defects"]:
        assert defect["classification"]
        assert defect["scenario"]
        assert defect["expected"]
        assert defect["observed"]
        assert defect["root_cause"]
        assert defect["owner_cell"]
        assert defect["fix_required"]
        assert defect["retest"]


def test_resolved_defects_are_preserved_as_regressions_not_deleted():
    resolved = {item["id"]: item for item in _manifest()["resolved_defects"]}
    assert set(resolved) == {"BUG-GP-001", "BUG-GP-003"}
    assert resolved["BUG-GP-001"]["main_sha"] == CURRENT_MAIN
    assert resolved["BUG-GP-003"]["main_sha"] == CURRENT_MAIN


def test_integration_handoffs_are_minimum_combinations_not_merge_authority():
    manifest = _manifest()
    handoffs = manifest["integration_lab_handoffs"]
    assert {h["handoff_id"] for h in handoffs} == {"INT-GP-01","INT-GP-02","INT-GP-03","INT-GP-04"}
    for handoff in handoffs:
        assert handoff["required_modules"]
        assert handoff["minimum_combination"]
        assert handoff["acceptance_tests"]
        assert handoff["expected_contracts"]
    policy = manifest["release_policy"]
    assert policy["branch_candidate_is_not_available_in_product"] is True
    assert policy["fixture_pass_is_not_live_pass"] is True
    assert policy["live_pass_is_not_deployed_pass"] is True
    assert policy["historical_pass_is_not_current_main_pass"] is True


def test_validation_record_separates_historical_combination_from_current_main():
    record = _load(VALIDATION)
    assert record["canonical_main"]["sha"] == CURRENT_MAIN
    assert record["canonical_main"]["product_status"] == "NOT_FULLY_ACCEPTED"
    assert record["canonical_main"]["authenticated_e2e"] == "PASS"
    historical = record["gp01_historical_combination"]
    assert historical["positive_path_result"] == "PASS_L4_FIXTURE_CANDIDATE"
    assert historical["full_golden_path_result"] == "FAIL"
    assert historical["not_current_main_acceptance"] is True
    assert record["current_gp01"]["overall"] == "GATED"
    assert record["current_main_deployed_truth"]["root_cause"] == "RESOLVED_FOR_CURRENT_MAIN"
