import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "acceptance" / "integration_manifest.json"

MATRIX_STATES = {"PASS", "FAIL", "GATED", "NOT_IMPLEMENTED", "NOT_APPLICABLE"}
COMPLETENESS_STATES = {"IMPLEMENTED", "ACCEPTED", "INTEGRATION_BLOCKED", "NOT_IMPLEMENTED", "FUTURE"}


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_acceptance_manifest_is_bound_to_explicit_main_baseline_and_no_merge_policy():
    manifest = _manifest()
    assert manifest["baseline"]["head_sha"] == "52e011083545a2e69526cd8e0a294cfb61682884"
    assert manifest["baseline"]["automatic_merge"] is False
    assert manifest["baseline"]["production_mutation"] is False
    assert manifest["baseline"]["master_queue_mutation"] is False


def test_product_completeness_uses_only_contract_states():
    manifest = _manifest()
    expected = {
        "DISCOVER", "SAVE", "COMPARE", "REQUIREMENTS", "DOCUMENTS", "READINESS",
        "EVIDENCE", "MILESTONES", "ECONOMICS", "MOBILIZATION", "BANGS",
        "DECISION", "WORKSPACE", "OUTCOME", "BUYER", "LIFECYCLE",
    }
    assert set(manifest["product_completeness"]) == expected
    for capability, record in manifest["product_completeness"].items():
        assert record["implementation"] in COMPLETENESS_STATES, capability
        assert record["acceptance"] in MATRIX_STATES, capability


def test_matrix_never_uses_unapproved_success_vocabulary():
    manifest = _manifest()
    assert manifest["acceptance_matrix_scope"] == "CURRENT_MAIN"
    dimensions = ("domain", "combination", "api", "tenant", "system", "live")
    for row in manifest["acceptance_matrix"]:
        for dimension in dimensions:
            assert row[dimension] in MATRIX_STATES, (row["journey"], dimension, row[dimension])


def test_release_subset_contains_truth_critical_smokes_and_no_false_green():
    manifest = _manifest()
    subset = {item["id"]: item for item in manifest["release_golden_subset"]}
    assert set(subset) == {
        "RELEASE_GOLDEN_01",
        "RELEASE_GOLDEN_02",
        "RELEASE_GOLDEN_03",
        "RELEASE_GOLDEN_04",
        "RELEASE_GOLDEN_05",
        "RELEASE_GOLDEN_06",
    }
    assert subset["RELEASE_GOLDEN_03"]["status"] == "PASS"
    assert subset["RELEASE_GOLDEN_03"]["scope"] == "deterministic API fixture"
    assert subset["RELEASE_GOLDEN_04"]["status"] == "FAIL"
    assert "expired opportunity may remain is_actionable=true" in subset["RELEASE_GOLDEN_04"]["blocking"]
    assert subset["RELEASE_GOLDEN_01"]["status"] != "PASS"
    assert subset["RELEASE_GOLDEN_02"]["status"] != "PASS"


def test_every_defect_has_owner_fix_and_retest_contract():
    for defect in _manifest()["defects"]:
        assert defect["classification"]
        assert defect["scenario"]
        assert defect["expected"]
        assert defect["observed"]
        assert defect["root_cause"]
        assert defect["owner_cell"]
        assert defect["fix_required"]
        assert defect["retest"]


def test_integration_handoffs_are_minimum_combinations_not_merge_authority():
    manifest = _manifest()
    handoffs = manifest["integration_lab_handoffs"]
    assert {h["handoff_id"] for h in handoffs} == {"INT-GP-01", "INT-GP-02", "INT-GP-03", "INT-GP-04"}
    for handoff in handoffs:
        assert handoff["required_modules"]
        assert handoff["minimum_combination"]
        assert handoff["acceptance_tests"]
        assert handoff["expected_contracts"]
    assert manifest["release_policy"]["branch_candidate_is_not_available_in_product"] is True
    assert manifest["release_policy"]["fixture_pass_is_not_live_pass"] is True
    assert manifest["release_policy"]["live_pass_is_not_deployed_pass"] is True
