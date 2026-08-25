import os

import preload
from source_registry import SOURCES, active_sources, production_gate_reasons


def test_canadabuys_registry_is_ready_but_not_active_by_default():
    meta = SOURCES["CA_CANADABUYS"]
    assert meta["status"] == "ready"
    assert meta["legal_reuse"] == "GREEN"
    assert meta["machine_access"] == "VERIFIED"
    assert meta["adapter"] == "CanadaBuysConnector"
    assert meta["expected_refresh_minutes"] == 120
    assert meta["realtime_capable"] is False
    assert set(meta["capabilities"]) == {"incremental_sync", "amendments", "lifecycle"}
    assert production_gate_reasons("CA_CANADABUYS") == ()
    assert "CA_CANADABUYS" not in active_sources()


def test_canadabuys_runtime_opt_in_is_separate_from_registry_readiness(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert preload._global_source_enabled("CA_CANADABUYS") is False
    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "CA_CANADABUYS")
    assert preload._global_source_enabled("CA_CANADABUYS") is True
    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "CO_SECOP")
    assert preload._global_source_enabled("CA_CANADABUYS") is False
