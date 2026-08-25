import pytest

import shared_family_runtime as runtime


class DummyPreload:
    @staticmethod
    def _global_source_enabled(source):
        return source == "EC_SERCOP"

    @staticmethod
    def _record_blocked_global_source(source):
        return source


class DummyApp:
    pass


def test_shared_family_runtime_delegates_with_canonical_gate_callbacks():
    captured = {}

    def fetch_incremental(*, watermark=None):
        return [], watermark

    def installer(app_module, **kwargs):
        captured["app"] = app_module
        captured.update(kwargs)
        return "installed"

    result = runtime.install_shared_family_source(
        DummyApp,
        DummyPreload,
        source="ec_sercop",
        fetch_incremental=fetch_incremental,
        installer=installer,
    )

    assert result == "installed"
    assert captured["app"] is DummyApp
    assert captured["source"] == "EC_SERCOP"
    assert captured["fetch_incremental"] is fetch_incremental
    assert captured["source_enabled"] is DummyPreload._global_source_enabled
    assert captured["record_blocked"] is DummyPreload._record_blocked_global_source


def test_shared_family_runtime_refuses_source_outside_family_registry():
    with pytest.raises(ValueError, match="not registered in a shared source family"):
        runtime.install_shared_family_source(
            DummyApp,
            DummyPreload,
            source="CA_CANADABUYS",
            fetch_incremental=lambda **_: ([], None),
            installer=lambda *_args, **_kwargs: None,
        )


def test_shared_family_runtime_refuses_invalid_fetcher():
    with pytest.raises(TypeError, match="fetcher must be callable"):
        runtime.install_shared_family_source(
            DummyApp,
            DummyPreload,
            source="EC_SERCOP",
            fetch_incremental=None,
            installer=lambda *_args, **_kwargs: None,
        )


def test_shared_family_runtime_checks_family_fitness_before_install(monkeypatch):
    called = {"installer": False}

    def fail_health():
        raise RuntimeError("family drift")

    def installer(*_args, **_kwargs):
        called["installer"] = True

    monkeypatch.setattr(runtime, "assert_shared_family_health", fail_health)
    with pytest.raises(RuntimeError, match="family drift"):
        runtime.install_shared_family_source(
            DummyApp,
            DummyPreload,
            source="EC_SERCOP",
            fetch_incremental=lambda **_: ([], None),
            installer=installer,
        )
    assert called["installer"] is False
