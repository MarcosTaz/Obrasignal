import canada_buys_runtime


def test_runtime_wiring_uses_global_source_gate_and_generic_plugin(monkeypatch):
    calls = {}

    def fake_install(app_module, **kwargs):
        calls["app_module"] = app_module
        calls.update(kwargs)
        return "wrapped"

    monkeypatch.setattr(canada_buys_runtime, "install_incremental_source", fake_install)

    assert canada_buys_runtime.install() == "wrapped"
    assert calls["app_module"] is canada_buys_runtime._app
    assert calls["source"] == "CA_CANADABUYS"
    assert calls["fetch_incremental"] is canada_buys_runtime.fetch_canadabuys_tenders
    assert calls["source_enabled"] is canada_buys_runtime._preload._global_source_enabled
    assert calls["record_blocked"] is canada_buys_runtime._preload._record_blocked_global_source
