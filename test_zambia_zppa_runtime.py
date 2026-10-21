import types

import zambia_zppa_runtime


def test_runtime_installer_delegates_to_incremental_plugin(monkeypatch):
    captured = {}

    def fake_install(app_module, **kwargs):
        captured["app"] = app_module
        captured.update(kwargs)
        return "installed"

    monkeypatch.setattr(zambia_zppa_runtime, "install_incremental_source", fake_install)
    app = types.SimpleNamespace()
    enabled = lambda source: source == "ZM_ZPPA"
    blocked = lambda source: None

    result = zambia_zppa_runtime.install_zambia_zppa_runtime(
        app,
        source_enabled=enabled,
        record_blocked=blocked,
    )

    assert result == "installed"
    assert captured["app"] is app
    assert captured["source"] == "ZM_ZPPA"
    assert captured["fetch_incremental"] is zambia_zppa_runtime.fetch_zm_tenders
    assert captured["source_enabled"] is enabled
    assert captured["record_blocked"] is blocked


def test_runtime_installer_requires_explicit_gate_callbacks():
    app = types.SimpleNamespace()
    try:
        zambia_zppa_runtime.install_zambia_zppa_runtime(app, source_enabled=None, record_blocked=lambda source: None)
    except TypeError as exc:
        assert "explicit gate" in str(exc)
    else:
        raise AssertionError("missing source gate must be rejected")
