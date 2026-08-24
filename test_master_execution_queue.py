from master_execution_queue import (
    CANONICAL_QUEUE_NAME,
    CURRENT_ITEM_ID,
    MASTER_EXECUTION_QUEUE,
    current_item,
    executable_after_current,
    next_executable_after_current,
    next_item_after_current,
    queue_ids,
)


def _by_id():
    return {item.id: item for item in MASTER_EXECUTION_QUEUE}


def test_exactly_one_canonical_active_item():
    assert CANONICAL_QUEUE_NAME == "OBRASIGNAL_MASTER_EXECUTION_QUEUE"
    active = [item for item in MASTER_EXECUTION_QUEUE if item.state == "ACTIVE"]
    assert len(active) == 1
    assert active[0].id == CURRENT_ITEM_ID == "Q040_CANADA_BUYS"
    assert current_item() == active[0]


def test_brazil_is_gated_without_blocking_current_canada_execution():
    items = _by_id()
    assert items["Q000_SCOPE_REBASE"].state == "DONE"
    assert items["Q010_BR_PNCP_DISCOVERY"].state == "DONE"
    assert items["Q020_SIGNAL_CONTRACT_V1"].state == "DONE"
    assert items["Q030_BR_PNCP_PCA"].state == "GATED"
    assert "transport reliability" in items["Q030_BR_PNCP_PCA"].reason
    assert items["Q040_CANADA_BUYS"].state == "ACTIVE"
    assert "Q030_BR_PNCP_PCA" not in items["Q070_SHARED_FAMILIES"].dependencies


def test_queue_is_total_order_with_unique_ids_and_backward_dependencies():
    ids = queue_ids()
    assert len(ids) == len(set(ids))
    position = {item_id: index for index, item_id in enumerate(ids)}
    for item in MASTER_EXECUTION_QUEUE:
        for dependency in item.dependencies:
            assert dependency in position
            assert position[dependency] < position[item.id]


def test_single_master_priority_chooses_us_after_current_canada():
    ready = executable_after_current()
    assert ready == next_executable_after_current()
    assert "Q030_BR_PNCP_PCA" not in {item.id for item in ready}
    assert all(item.state == "QUEUED" for item in ready)
    assert [item.id for item in ready[:3]] == [
        "Q050_US_SAM",
        "Q060_CHILE_MERCADOPUBLICO",
        "Q080_EVIDENCE_GRAPH_V1",
    ]
    assert next_item_after_current().id == "Q050_US_SAM"


def test_all_six_target_layers_are_in_same_queue():
    domains = {item.domain for item in MASTER_EXECUTION_QUEUE}
    assert {"SIGNAL", "OFFICE", "DNA", "SHADOW", "COMMAND", "ACTION"}.issubset(domains)


def test_trade_mobilization_and_microworks_are_in_the_same_master_queue():
    ids = set(queue_ids())
    required = {
        "Q210_SUPPLY_EDGE",
        "Q212_TRUSTBRIDGE_RESEARCH",
        "Q214_TRADE_AGENT_ARCHITECTURE",
        "Q216_SUPPLIER_PORTAL",
        "Q218_TRADE_LOOP_PILOT",
        "Q222_MOBILIZE_RESEARCH",
        "Q224_SITE_READY_RESEARCH",
        "Q226_CAPACITY_OPTIMIZER_RESEARCH",
        "Q228_CREW_ECONOMICS_RESEARCH",
        "Q229_DEAD_TIME_RESEARCH",
        "Q231_CAPACITY_UNIT_SERVICES",
        "Q232_MICROWORKS_SOURCE_VALIDATION",
        "Q233_MICROWORKS_ECONOMIC_MATCHING",
        "Q234_CONTINUOUS_OPPORTUNITY_HUNTING",
        "Q235_MICROWORKS_ACTION_PILOT",
    }
    assert required.issubset(ids)


def test_mobilization_capabilities_depend_on_operational_intelligence_not_feature_bloat():
    items = _by_id()
    assert set(items["Q222_MOBILIZE_RESEARCH"].dependencies) == {
        "Q090_COMPANY_STATE_CONTRACT",
        "Q160_SHADOW_PORTFOLIO_PROTOTYPE",
        "Q180_ACTION_ARCHITECTURE",
        "Q210_SUPPLY_EDGE",
    }
    assert "Q222_MOBILIZE_RESEARCH" in items["Q224_SITE_READY_RESEARCH"].dependencies
    assert {
        "Q140_CONTRACTOR_DNA_V1",
        "Q160_SHADOW_PORTFOLIO_PROTOTYPE",
        "Q190_FUTURE_DEMAND_ASSET_CLOCK",
        "Q210_SUPPLY_EDGE",
        "Q222_MOBILIZE_RESEARCH",
    }.issubset(set(items["Q226_CAPACITY_OPTIMIZER_RESEARCH"].dependencies))
    assert {
        "Q130_CREW_CAPACITY_SENSOR",
        "Q140_CONTRACTOR_DNA_V1",
        "Q222_MOBILIZE_RESEARCH",
    }.issubset(set(items["Q228_CREW_ECONOMICS_RESEARCH"].dependencies))
    assert {
        "Q120_OFFICE_SENSOR_RESEARCH",
        "Q130_CREW_CAPACITY_SENSOR",
        "Q170_COMMAND_NEXT_BEST_ACTION",
        "Q224_SITE_READY_RESEARCH",
    }.issubset(set(items["Q229_DEAD_TIME_RESEARCH"].dependencies))


def test_microworks_cannot_bypass_capacity_economics_trust_or_action_gates():
    items = _by_id()
    assert {
        "Q090_COMPANY_STATE_CONTRACT",
        "Q120_OFFICE_SENSOR_RESEARCH",
        "Q130_CREW_CAPACITY_SENSOR",
    } == set(items["Q231_CAPACITY_UNIT_SERVICES"].dependencies)
    assert {
        "Q020_SIGNAL_CONTRACT_V1",
        "Q080_EVIDENCE_GRAPH_V1",
        "Q231_CAPACITY_UNIT_SERVICES",
    } == set(items["Q232_MICROWORKS_SOURCE_VALIDATION"].dependencies)
    assert {
        "Q160_SHADOW_PORTFOLIO_PROTOTYPE",
        "Q170_COMMAND_NEXT_BEST_ACTION",
        "Q212_TRUSTBRIDGE_RESEARCH",
        "Q222_MOBILIZE_RESEARCH",
        "Q229_DEAD_TIME_RESEARCH",
        "Q231_CAPACITY_UNIT_SERVICES",
        "Q232_MICROWORKS_SOURCE_VALIDATION",
    } == set(items["Q233_MICROWORKS_ECONOMIC_MATCHING"].dependencies)
    assert {
        "Q120_OFFICE_SENSOR_RESEARCH",
        "Q180_ACTION_ARCHITECTURE",
        "Q229_DEAD_TIME_RESEARCH",
        "Q233_MICROWORKS_ECONOMIC_MATCHING",
    } == set(items["Q234_CONTINUOUS_OPPORTUNITY_HUNTING"].dependencies)
    assert {
        "Q214_TRADE_AGENT_ARCHITECTURE",
        "Q233_MICROWORKS_ECONOMIC_MATCHING",
        "Q234_CONTINUOUS_OPPORTUNITY_HUNTING",
    } == set(items["Q235_MICROWORKS_ACTION_PILOT"].dependencies)
    for item_id in {
        "Q231_CAPACITY_UNIT_SERVICES",
        "Q232_MICROWORKS_SOURCE_VALIDATION",
        "Q233_MICROWORKS_ECONOMIC_MATCHING",
        "Q234_CONTINUOUS_OPPORTUNITY_HUNTING",
        "Q235_MICROWORKS_ACTION_PILOT",
    }:
        assert items[item_id].state == "GATED"


def test_reverse_capacity_network_requires_trust_and_capacity_contract():
    items = _by_id()
    deps = set(items["Q270_LIVE_CAPACITY_NETWORK"].dependencies)
    assert "Q212_TRUSTBRIDGE_RESEARCH" in deps
    assert "Q231_CAPACITY_UNIT_SERVICES" in deps
    assert items["Q270_LIVE_CAPACITY_NETWORK"].state == "FUTURE"


def test_strategic_bangs_and_long_term_capabilities_are_queued():
    ids = set(queue_ids())
    required = {
        "Q110_DYNAMIC_ELIGIBILITY_RESEARCH",
        "Q150_SHADOW_PORTFOLIO_RESEARCH",
        "Q190_FUTURE_DEMAND_ASSET_CLOCK",
        "Q200_FORCED_DEMAND",
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
