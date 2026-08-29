import incremental_runtime_plugin as runtime_plugin
import finland_runtime


class FakeConn:
    def close(self):
        pass


def test_finland_runtime_installer_is_available():
    assert callable(finland_runtime.install)
    assert finland_runtime.SOURCE == "FI_HILMA"


def test_finland_runtime_stages_plan_but_emits_only_tender(monkeypatch):
    staged = []
    monkeypatch.setattr(finland_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(finland_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(finland_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(finland_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    tender = {"source": "FI_HILMA", "external_id": "t1", "signal_type": "TENDER"}
    plan = {"source": "FI_HILMA", "external_id": "p1", "signal_type": "PROCUREMENT_PLAN"}
    monkeypatch.setattr(finland_runtime, "fetch_finland_hilma", lambda *, watermark=None: ([tender, plan], "new"))

    finland_runtime.install()
    rows = finland_runtime._app.fetch_base()

    assert rows == [tender]
    assert staged == [("FI_HILMA", [tender, plan], "new")]


def test_finland_runtime_source_failure_does_not_remove_existing_rows(monkeypatch):
    staged = []
    health = []
    base = {"source": "TED", "external_id": "ted-safe"}
    monkeypatch.setattr(finland_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(finland_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(finland_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(finland_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def unavailable(*, watermark=None):
        assert watermark == "old"
        raise RuntimeError("HILMA unavailable")

    monkeypatch.setattr(finland_runtime, "fetch_finland_hilma", unavailable)
    finland_runtime.install()
    rows = finland_runtime._app.fetch_base()

    assert rows == [base]
    assert staged == []
    assert health and health[0][0] == "FI_HILMA"
    assert health[0][1]["success"] is False
