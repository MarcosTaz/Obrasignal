from master_execution_queue import CURRENT_ITEM_ID, MASTER_EXECUTION_QUEUE, queue_ids


def test_trade_capabilities_share_the_single_master_queue_without_interrupting_brazil():
    assert CURRENT_ITEM_ID == "Q030_BR_PNCP_PCA"
    ids = queue_ids()
    expected = (
        "Q210_SUPPLY_EDGE",
        "Q212_TRUSTBRIDGE_RESEARCH",
        "Q214_TRADE_AGENT_ARCHITECTURE",
        "Q216_SUPPLIER_PORTAL",
        "Q218_TRADE_LOOP_PILOT",
    )
    assert all(item_id in ids for item_id in expected)
    positions = [ids.index(item_id) for item_id in expected]
    assert positions == sorted(positions)


def test_trade_loop_is_gated_by_supply_trust_authorization_portal_shadow_and_command():
    items = {item.id: item for item in MASTER_EXECUTION_QUEUE}
    assert set(items["Q212_TRUSTBRIDGE_RESEARCH"].dependencies) >= {
        "Q080_EVIDENCE_GRAPH_V1",
        "Q100_OUTCOME_GRAPH_V1",
        "Q210_SUPPLY_EDGE",
    }
    assert set(items["Q214_TRADE_AGENT_ARCHITECTURE"].dependencies) >= {
        "Q180_ACTION_ARCHITECTURE",
        "Q210_SUPPLY_EDGE",
        "Q212_TRUSTBRIDGE_RESEARCH",
    }
    assert set(items["Q218_TRADE_LOOP_PILOT"].dependencies) >= {
        "Q160_SHADOW_PORTFOLIO_PROTOTYPE",
        "Q170_COMMAND_NEXT_BEST_ACTION",
        "Q210_SUPPLY_EDGE",
        "Q212_TRUSTBRIDGE_RESEARCH",
        "Q214_TRADE_AGENT_ARCHITECTURE",
        "Q216_SUPPLIER_PORTAL",
    }
    assert items["Q218_TRADE_LOOP_PILOT"].target_stage == "PILOT"
