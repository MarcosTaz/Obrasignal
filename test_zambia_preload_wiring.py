import preload
from source_registry import SOURCES, production_gate_reasons, production_ready_sources


def test_zambia_passes_gate_but_requires_explicit_runtime_request(monkeypatch):
    assert SOURCES["ZM_ZPPA"]["status"] == "ready"
    assert production_gate_reasons("ZM_ZPPA") == ()
    assert "ZM_ZPPA" in production_ready_sources()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert preload._global_source_enabled("ZM_ZPPA") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "ZM_ZPPA")
    assert preload._global_source_enabled("ZM_ZPPA") is True


def test_zambia_is_installed_in_preload_incremental_chain():
    installed = set(getattr(preload._app.fetch_base, "_obrasignal_incremental_sources", ()))
    assert "ZM_ZPPA" in installed
