from source_registry import SOURCES, production_gate_reasons, production_ready_sources, wave_sources


def test_finland_hilma_registry_contract():
    source = SOURCES["FI_HILMA"]
    assert source["country"] == "FIN"
    assert source["kind"] == "OFFICIAL_AZURE_SEARCH_API"
    assert source["access"] == "free_self_service_subscription_key"
    assert source["adapter"] == "HilmaAVPConnector"
    assert source["signal_types"] == ("PROCUREMENT_PLAN", "TENDER")
    assert set(source["capabilities"]) == {"search", "incremental_sync", "plans"}
    assert source["wave"] is None
    assert production_gate_reasons("FI_HILMA") == ()
    assert "FI_HILMA" in production_ready_sources()
    assert "FI_HILMA" not in wave_sources(1)
