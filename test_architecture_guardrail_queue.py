from master_execution_queue import CURRENT_ITEM_ID, MASTER_EXECUTION_QUEUE, executable_after_current


def test_modular_architecture_guardrail_is_in_single_master_queue_without_preempting_canada():
    items = {item.id: item for item in MASTER_EXECUTION_QUEUE}
    guardrail = items["Q005_MODULAR_ARCHITECTURE_GUARDRAILS"]
    assert guardrail.state == "DONE"
    assert guardrail.domain == "ARCHITECTURE"
    assert CURRENT_ITEM_ID == "Q040_CANADA_BUYS"
    assert items[CURRENT_ITEM_ID].state == "ACTIVE"
    assert executable_after_current()[0].id == "Q050_US_SAM"
