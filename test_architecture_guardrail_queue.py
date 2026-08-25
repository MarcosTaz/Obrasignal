from master_execution_queue import CURRENT_ITEM_ID, MASTER_EXECUTION_QUEUE, executable_after_current


def test_modular_architecture_guardrail_stays_done_without_preempting_current_queue_item():
    items = {item.id: item for item in MASTER_EXECUTION_QUEUE}
    guardrail = items["Q005_MODULAR_ARCHITECTURE_GUARDRAILS"]
    assert guardrail.state == "DONE"
    assert guardrail.domain == "ARCHITECTURE"
    assert items["Q040_CANADA_BUYS"].state == "DONE"
    assert items["Q050_US_SAM"].state == "DONE"
    assert items["Q060_CHILE_MERCADOPUBLICO"].state == "GATED"
    assert CURRENT_ITEM_ID == "Q070_SHARED_FAMILIES"
    assert items[CURRENT_ITEM_ID].state == "ACTIVE"
    assert executable_after_current()[0].id == "Q080_EVIDENCE_GRAPH_V1"
