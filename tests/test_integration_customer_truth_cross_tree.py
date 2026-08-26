import json
from pathlib import Path


MATRIX = Path(__file__).resolve().parents[1] / "integration_customer_truth_cross_tree.json"


def _matrix():
    return json.loads(MATRIX.read_text())


def test_cross_tree_has_no_false_success_promotions():
    data = _matrix()
    cases = {item["input"]: item["forbidden_output"] for item in data["required_no_promotion_cases"]}
    assert cases["SOURCE_UNKNOWN_OR_PARTIAL_OR_STALE"] == "ZERO_MARKET_OR_TRUTHFUL_NO_MATCH_WITHOUT_COVERAGE_PROOF"
    assert cases["MISSING_DECISION_WORK_AFTER_RESTART"] == "ZERO_OPPORTUNITY_OR_NO_RELEVANT_MATCH"
    assert cases["STALE_DECISION_RULE"] == "CURRENT_RADAR_MATCH_OR_NEW_HIGH_MATCH_EVENT"
    assert cases["SCHEDULE_ACCEPTED_OR_PROVIDER_ACCEPTED"] == "DEVICE_DELIVERED_OR_CUSTOMER_VALUE"


def test_every_customer_path_break_remains_explicit():
    data = _matrix()
    by_stage = {item["stage"]: item["status"] for item in data["path"]}
    assert by_stage["DECISION_DISCOVERY"] == "BROKEN_RESTART_REDISCOVERY"
    assert by_stage["DECISION_CURRENTNESS"] == "BROKEN_SEMANTIC_FRESHNESS"
    assert by_stage["EVENT_CAUSAL_PARENT"] == "BROKEN_PARENTAGE"
    assert by_stage["LOCAL_DELIVERY_TRUTH"] == "BROKEN_FALSE_COMPLETION"
    assert by_stage["CUSTOMER_VALUE"] == "BROKEN_COMPOSITION_ON_MAIN"
    assert data["global_classification"] == "NOT_END_TO_END_GREEN"


def test_provider_and_customer_observation_stay_external_wait():
    data = _matrix()
    assert data["external_wait_only"] == [
        "ACTUAL_DEVICE_PROVIDER_DELIVERY_EVIDENCE",
        "CUSTOMER_OBSERVED_OUTCOME_EVIDENCE",
    ]
    principles = set(data["principles"])
    assert "PROVIDER_ACCEPTED != DEVICE_DELIVERED" in principles
    assert "DELIVERY_MARKER != CUSTOMER_VALUE" in principles
