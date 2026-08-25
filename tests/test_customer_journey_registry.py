import json
from pathlib import Path

from customer_journey_audit import FACTORY_TITLE, load_registry, validate_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "customer_journey_registry.json"
CANONICAL_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"


def _by_step():
    registry = load_registry(REGISTRY)
    return registry, {edge["STEP"]: edge for edge in registry["edges"]}


def test_registry_is_fail_closed_and_uses_exact_factory_title():
    registry = load_registry(REGISTRY)
    assert registry["factory_title"] == FACTORY_TITLE
    assert registry["canonical_main_sha"] == CANONICAL_MAIN
    assert validate_registry(registry) == []


def test_every_edge_is_classified_against_the_same_exact_canonical_main():
    registry = load_registry(REGISTRY)
    assert registry["edges"]
    assert all(edge["CURRENT_SHA"] == CANONICAL_MAIN for edge in registry["edges"])
    assert len({edge["STEP"] for edge in registry["edges"]}) == len(registry["edges"])


def test_canonical_zero_state_remains_broken_until_noncanonical_composition_is_accepted():
    _, edges = _by_step()
    zero = edges["RADAR_ZERO_STATE"]
    assert zero["STATUS"] == "BROKEN"
    assert "ZERO" in zero["EXPECTED_CUSTOMER_TRUTH"].upper()
    assert "MARKET" in zero["EXPECTED_CUSTOMER_TRUTH"].upper()
    assert "UNKNOWN" in zero["EXPECTED_CUSTOMER_TRUTH"].upper()
    assert any("#399" in evidence and "non-canonical" in evidence.lower() for evidence in zero["EVIDENCE"])
    assert "Golden" in zero["REOPEN_CONDITION"]


def test_profile_to_radar_is_not_overclaimed_as_full_first_value():
    _, edges = _by_step()
    assert edges["PROFILE_TO_RADAR"]["STATUS"] == "PARTIAL"
    assert edges["FIRST_VALUE"]["STATUS"] == "PARTIAL"
    assert any("bootstrap_account" in evidence for evidence in edges["PROFILE_TO_RADAR"]["CURRENT_TEST"])


def test_saved_is_prebuild_not_canonical_customer_capability():
    _, edges = _by_step()
    saved = edges["SAVE_REVIEW"]
    assert saved["STATUS"] == "PREBUILD"
    assert any("#150" in evidence for evidence in saved["EVIDENCE"])
    assert "reanchor" in saved["BLOCKER"].lower()
    assert saved["REOPEN_CONDITION"]


def test_workflow_persistence_is_not_equated_with_real_world_progress():
    _, edges = _by_step()
    workflow = edges["WORKFLOW_PURSUIT"]
    assert workflow["STATUS"] == "PARTIAL"
    assert "never claims real-world bid progress" in workflow["EXPECTED_CUSTOMER_TRUTH"]


def test_repeat_value_stays_unknown_without_a_deterministic_second_value_scenario():
    _, edges = _by_step()
    repeat_value = edges["REPEAT_VALUE"]
    assert repeat_value["STATUS"] == "DISCOVERED_UNKNOWN"
    assert any("no canonical deterministic repeat-value scenario" in item for item in repeat_value["CURRENT_TEST"])


def test_no_fake_aggregate_customer_value_score_exists():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    forbidden = {"score", "percentage", "overall_score", "journey_score", "completion_percent"}
    assert forbidden.isdisjoint(registry)
