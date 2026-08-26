import json
from pathlib import Path


MATRIX = Path(__file__).resolve().parents[1] / "integration_delivery_recovery_matrix.json"


def _matrix():
    return json.loads(MATRIX.read_text())


def test_cross_tree_matrix_never_promotes_partial_delivery_truth():
    data = _matrix()
    forbidden = {tuple(pair) for pair in data["forbidden_promotions"]}
    assert ("UNKNOWN_EXTERNAL_ATTEMPT", "NEVER_SENT") in forbidden
    assert ("SCHEDULED_NOT_DELIVERED", "DELIVERED") in forbidden
    assert ("PROVIDER_ACCEPTED", "DEVICE_DELIVERED") in forbidden
    assert ("RECEIPT_RECEIVED", "CUSTOMER_OBSERVED") in forbidden
    assert ("DELIVERY_MARKER", "FIRST_VALUE") in forbidden


def test_known_failing_before_boundaries_remain_explicit_and_independent():
    data = _matrix()
    by_evidence = {item["evidence"].split("@")[0].split()[0]: item for item in data["boundaries"]}
    assert by_evidence["#485"]["risk"] == "LOST_WORK"
    assert by_evidence["#497"]["risk"] == "UNTRACEABLE_CAUSAL_PARENT"
    assert by_evidence["#487"]["risk"] == "DUPLICATE_EXTERNAL_EFFECT"
    assert by_evidence["#509"]["risk"] == "RECEIPT_FANOUT_UNTRACEABLE_PARENT"
    assert by_evidence["#489"]["risk"] == "FALSE_COMPLETION"


def test_external_truth_stays_external_wait():
    data = _matrix()
    assert data["preserved_external_wait"] == [
        "ACTUAL_DEVICE_DELIVERY_PROOF",
        "CUSTOMER_OBSERVED_PROOF",
    ]
    principles = set(data["principles"])
    assert "PROVIDER_ACCEPTED != DEVICE_DELIVERED" in principles
    assert "RECEIPT_RECEIVED != CUSTOMER_OBSERVED" in principles
