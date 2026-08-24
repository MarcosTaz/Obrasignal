from master_execution_queue import (
    CANONICAL_QUEUE_NAME,
    CURRENT_ITEM_ID,
    MASTER_EXECUTION_QUEUE,
    current_item,
    next_executable_after_current,
    queue_ids,
)


def test_exactly_one_canonical_active_item():
    assert CANONICAL_QUEUE_NAME == "OBRASIGNAL_MASTER_EXECUTION_QUEUE"
    active = [item for item in MASTER_EXECUTION_QUEUE if item.state == "ACTIVE"]
    assert len(active) == 1
    assert active[0].id == CURRENT_ITEM_ID == "Q010_BR_PNCP_DISCOVERY"
    assert current_item() == active[0]


def test_queue_is_total_order_with_unique_ids_and_backward_dependencies():
    ids = queue_ids()
    assert len(ids) == len(set(ids))
    position = {item_id: index for index, item_id in enumerate(ids)}
    for item in MASTER_EXECUTION_QUEUE:
        for dependency in item.dependencies:
            assert dependency in position
            assert position[dependency] < position[item.id]


def test_future_architecture_does_not_jump_current_execution():
    executable = next_executable_after_current()
    assert [item.id for item in executable] == ["Q020_SIGNAL_CONTRACT_V1"]


def test_all_six_target_layers_are_in_same_queue():
    domains = {item.domain for item in MASTER_EXECUTION_QUEUE}
    assert {"SIGNAL", "OFFICE", "DNA", "SHADOW", "COMMAND", "ACTION"}.issubset(domains)


def test_strategic_bangs_and_long_term_capabilities_are_queued():
    ids = set(queue_ids())
    required = {
        "Q110_DYNAMIC_ELIGIBILITY_RESEARCH",
        "Q150_SHADOW_PORTFOLIO_RESEARCH",
        "Q190_FUTURE_DEMAND_ASSET_CLOCK",
        "Q200_FORCED_DEMAND",
        "Q210_SUPPLY_EDGE",
        "Q220_WORK_PACKAGE_RELEASE",
        "Q240_GROWTH_SIMULATOR",
        "Q250_RESCUE_MODE",
        "Q260_BENCHMARK_NETWORK",
        "Q270_LIVE_CAPACITY_NETWORK",
        "Q280_CHAIN_REACTION",
    }
    assert required.issubset(ids)


def test_maturity_targets_use_explicit_feature_gates():
    allowed = {"RESEARCH", "PROTOTYPE", "PILOT", "PRODUCTION"}
    assert all(item.target_stage in allowed for item in MASTER_EXECUTION_QUEUE)
    assert all(item.reason for item in MASTER_EXECUTION_QUEUE)
