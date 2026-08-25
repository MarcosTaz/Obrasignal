from incremental_runtime_plugin import _legacy_rows
from source_registry import SOURCES


def test_uk_registry_declares_one_source_with_plan_and_tender_signals():
    source = SOURCES["UK_PROCUREMENT"]
    assert source["source_id"] == "uk_find_a_tender_contracts_finder"
    assert source["status"] == "ready"
    assert source["legal_reuse"] == "GREEN"
    assert source["machine_access"] == "VERIFIED"
    assert source["signal_types"] == ("PROCUREMENT_PLAN", "TENDER")
    assert "plans" in source["capabilities"]
    assert "lifecycle" in source["capabilities"]
    assert source["adapter"] == "UKFindTenderLifecycleConnector"


def test_procurement_plan_is_staged_but_never_projected_as_legacy_tender():
    plan = {
        "source": "UK_PROCUREMENT",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": "ocds-h6vhtk-0512ab:notice:UK3",
    }
    tender = {
        "source": "UK_PROCUREMENT",
        "signal_type": "TENDER",
        "external_id": "ocds-h6vhtk-0512ab:lot:1",
    }
    assert _legacy_rows([plan, tender]) == [tender]
