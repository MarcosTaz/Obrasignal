from source_registry import SOURCES, production_gate_reasons


def test_zambia_source_is_registered_ready_but_not_implicitly_active():
    source = SOURCES["ZM_ZPPA"]
    assert source["country"] == "ZMB"
    assert source["status"] == "ready"
    assert source["legal_reuse"] == "GREEN"
    assert source["machine_access"] == "VERIFIED"
    assert source["adapter"] == "OCDSJSONLGzipSnapshotConnector"
    assert source["signal_types"] == ("TENDER",)
    assert source["realtime_capable"] is False
    assert source["wave"] is None
    assert production_gate_reasons("ZM_ZPPA") == ()
