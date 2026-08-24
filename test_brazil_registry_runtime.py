import brazil_runtime
from source_registry import SOURCES, production_gate_reasons, production_ready_sources


def test_brazil_registry_declares_only_proven_pca_plan_capabilities():
    source = SOURCES["BR_PNCP_PCA"]
    assert source["country"] == "BRA"
    assert source["source_id"] == "br_pncp_pca"
    assert source["kind"] == "OFFICIAL_PUBLIC_PCA_SEARCH_AND_API"
    assert source["access"] == "public_frontend_search_plus_documented_open_api"
    assert source["status"] == "ready"
    assert source["legal_reuse"] == "GREEN"
    assert source["machine_access"] == "VERIFIED"
    assert source["adapter"] == "BrazilPNCPPCAConnector"
    assert source["signal_types"] == ("PROCUREMENT_PLAN",)
    assert set(source["capabilities"]) == {"search", "incremental_sync", "detail", "plans"}
    assert source["wave"] == 2
    assert source["realtime_capable"] is True
    assert source["expected_refresh_minutes"] == 60
    assert source["stale_after_minutes"] == 180
    assert "historical_data" not in source["capabilities"]
    assert "lifecycle" not in source["capabilities"]
    assert "tenders" not in source["capabilities"]
    assert production_gate_reasons("BR_PNCP_PCA") == ()
    assert "BR_PNCP_PCA" in production_ready_sources()


def test_brazil_runtime_installs_only_through_existing_global_source_gate(monkeypatch):
    captured = {}

    def fake_install(app_module, **kwargs):
        captured["app"] = app_module
        captured.update(kwargs)
        return "wrapped"

    monkeypatch.setattr(brazil_runtime, "install_incremental_source", fake_install)
    result = brazil_runtime.install()

    assert result == "wrapped"
    assert captured["source"] == "BR_PNCP_PCA"
    assert captured["fetch_incremental"] is brazil_runtime.fetch_brazil_pncp_pca_plans
    assert captured["source_enabled"] is brazil_runtime._preload._global_source_enabled
    assert captured["record_blocked"] is brazil_runtime._preload._record_blocked_global_source
