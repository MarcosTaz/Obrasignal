from qatar_ashghal import AshghalOpenTenderConnector
from source_registry import SOURCES, active_sources, production_gate_reasons, production_ready_sources


def test_registry_declares_bounded_official_slice_without_runtime_enablement():
    meta = SOURCES["QA_ASHGHAL"]
    assert meta["country"] == "QAT"
    assert meta["official"] is True
    assert meta["machine_access"] == "VERIFIED"
    assert meta["legal_reuse"] == "YELLOW"
    assert meta["status"] == "planned"
    assert meta["adapter"] == "AshghalOpenTenderConnector"
    assert meta["signal_types"] == ("TENDER",)
    assert "QA_ASHGHAL" not in active_sources()
    assert "QA_ASHGHAL" not in production_ready_sources()


def test_registry_gate_is_legal_and_runtime_not_machine_access():
    reasons = production_gate_reasons("QA_ASHGHAL")
    assert "commercial_reuse_not_green" in reasons
    assert "runtime_not_enabled" in reasons
    assert "machine_access_not_verified" not in reasons
    assert "adapter_not_configured" not in reasons


def test_registry_named_adapter_exists_and_is_inert_until_called():
    connector = AshghalOpenTenderConnector(timeout=7)
    assert connector.source == "QA_ASHGHAL"
    assert connector.timeout == 7
