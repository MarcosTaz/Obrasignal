from factory_cloud.promotion_queue import build_promotion_queue


def test_portfolio_to_app_promotion_queue_is_fail_closed():
    queue = build_promotion_queue()
    by_id = {item.factory_id: item for item in queue}

    assert by_id["aviation-lease-entitlement-recovery"].state == "APP_REGISTERED"
    assert by_id["contractcredit"].state == "APP_REGISTERED"
    assert by_id["industrial-claims"].state == "APP_REGISTERED"
    assert by_id["industrial-claims"].maturity == "G2"
    assert by_id["industrial-claims"].blocker == ""

    assert by_id["warrantyguard"].state == "PROMOTION_BLOCKED"
    assert by_id["warrantyguard"].blocker == "canonical_application_source_truth_required"


def test_blocked_higher_maturity_verticals_are_prioritized_before_lower_maturity():
    blocked = [item for item in build_promotion_queue() if not item.app_registered]
    ranks = {"G6": 6, "G5": 5, "G4": 4, "G3": 3, "G2": 2, "G1": 1, "G0": 0, "UNASSESSED": -1}
    observed = [ranks[item.maturity] for item in blocked]
    assert observed == sorted(observed, reverse=True)
