from factory_cloud.pilot_safe_matrix import portfolio_matrix
from factory_cloud.pilot_safe_work import next_work, portfolio_work_queue, work_for_missing


def test_unregistered_factory_routes_source_truth_first():
    item = next_work("dealrecover", {"source_registered", "web_complete", "support_continuity"})
    assert item is not None
    assert item.evidence_key == "source_registered"
    assert item.task == "register_and_verify_canonical_source_truth"


def test_registered_vertical_routes_product_and_web_before_shadow_validation():
    items = work_for_missing("contractcredit", {"web_complete", "end_to_end_product", "shadow_validation"})
    assert [item.evidence_key for item in items] == ["end_to_end_product", "web_complete", "shadow_validation"]


def test_shared_work_wins_tie_before_vertical_work():
    matrix = [
        {"factory_id":"a","classification":"NOT_PILOT_SAFE","missing_evidence":["web_complete"]},
        {"factory_id":"b","classification":"NOT_PILOT_SAFE","missing_evidence":["end_to_end_product"]},
    ]
    queue = portfolio_work_queue(matrix)
    assert queue[0].evidence_key == "end_to_end_product"
    assert queue[1].evidence_key == "web_complete"


def test_real_portfolio_produces_source_work_and_only_remaining_recovery_blocker():
    queue = portfolio_work_queue(portfolio_matrix())
    pairs = {(item.factory_id, item.evidence_key) for item in queue}
    assert ("dealrecover", "source_registered") in pairs
    assert ("contractcredit", "billing_sandbox") in pairs
    assert ("aviation-lease-entitlement-recovery", "billing_sandbox") in pairs
    assert ("contractcredit", "web_complete") not in pairs
    assert ("aviation-lease-entitlement-recovery", "support_continuity") not in pairs
