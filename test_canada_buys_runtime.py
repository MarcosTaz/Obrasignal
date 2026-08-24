from types import SimpleNamespace

import canada_buys_runtime


def test_runtime_wiring_uses_registry_gate_and_generic_plugin(monkeypatch):
    calls = {}

    def fake_install(app_module, **kwargs):
        calls.update(kwargs)
        return "wrapped"

    monkeypatch.setattr(canada_buys_runtime, "install_incremental_source", fake_install)
    monkeypatch.setattr(canada_buys_runtime, "production_gate_reasons", lambda name: ())
    app = SimpleNamespace(fetch_base=lambda: [], db=lambda: None)
    blocked = lambda source: None

    assert canada_buys_runtime.install_canadabuys_runtime(app, record_blocked=blocked) == "wrapped"
    assert calls["source"] == "CA_CANADABUYS"
    assert calls["fetch_incremental"] is canada_buys_runtime.fetch_canadabuys_tenders
    assert calls["record_blocked"] is blocked
    assert calls["source_enabled"]("CA_CANADABUYS") is True
