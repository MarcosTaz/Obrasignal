import json
from pathlib import Path


MATRIX = Path(__file__).resolve().parents[1] / "integration_source_radar_truth_matrix.json"


def _matrix():
    return json.loads(MATRIX.read_text())


def test_uncertain_source_states_never_become_zero_market():
    data = _matrix()
    states = {item["source_state"]: item for item in data["states"]}
    for name in ("SOURCE_UNAVAILABLE", "SOURCE_STALE", "SOURCE_PARTIAL", "SOURCE_UNKNOWN"):
        assert "zero_market" in states[name]["forbidden_customer_claims"]
    assert data["cross_consumer_contract"]["source_unknown_partial_stale_never_equals_zero_market"] is True


def test_current_empty_is_still_not_market_absence_proof():
    data = _matrix()
    zero = next(item for item in data["states"] if item["source_state"] == "GENUINE_ZERO_RESULTS")
    assert zero["required_radar_truth"] == "observed_empty_current"
    assert "market_absence_proven" in zero["forbidden_customer_claims"]
    assert "zero_market_claim_allowed" in zero["forbidden_customer_claims"]


def test_current_global_classification_stays_fail_closed():
    data = _matrix()
    status = data["current_classification"]
    assert status["source_health_producer"] == "GREEN_ON_399_EXACT_TREE"
    assert status["radar_consumer"] == "BROKEN_BY_508"
    assert status["global_end_to_end"] == "NOT_GREEN"
    assert data["cross_consumer_contract"]["public_source_health_only_no_parallel_truth"] is True
