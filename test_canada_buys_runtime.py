import pytest

import canada_buys_runtime


class FakeApp:
    pass


def test_runtime_wiring_uses_explicit_opt_in_gate_and_generic_plugin(monkeypatch):
    calls = {}

    def fake_install(app_module, **kwargs):
        calls["app_module"] = app_module
        calls.update(kwargs)
        return "wrapped"

    source_enabled = lambda name: name == "CA_CANADABUYS"
    record_blocked = lambda name: None
    monkeypatch.setattr(canada_buys_runtime, "install_incremental_source", fake_install)

    app = FakeApp()
    assert canada_buys_runtime.install_canadabuys_runtime(
        app,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    ) == "wrapped"
    assert calls["app_module"] is app
    assert calls["source"] == "CA_CANADABUYS"
    assert calls["fetch_incremental"] is canada_buys_runtime.fetch_canadabuys_tenders
    assert calls["source_enabled"] is source_enabled
    assert calls["record_blocked"] is record_blocked


def test_runtime_requires_explicit_gate_callbacks():
    with pytest.raises(TypeError, match="explicit gate"):
        canada_buys_runtime.install_canadabuys_runtime(FakeApp(), source_enabled=None, record_blocked=lambda name: None)
