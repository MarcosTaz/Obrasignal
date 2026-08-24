import incremental_runtime_plugin as runtime_plugin
import germany_runtime


class FakeConn:
    def close(self):
        pass


def test_germany_runtime_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert germany_runtime._preload._global_source_enabled("SERVICE_BUND_DE") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "SERVICE_BUND_DE")
    assert germany_runtime._preload._global_source_enabled("SERVICE_BUND_DE") is True


def test_germany_runtime_is_idempotent_and_persists_catchup_cursor(monkeypatch):
    staged, health, calls = [], [], []
    base = {"source": "BASE", "external_id": "base-1"}
    monkeypatch.setattr(germany_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(germany_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(germany_runtime._preload, "_global_source_enabled", lambda source: source == "SERVICE_BUND_DE")
    monkeypatch.setattr(germany_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "de-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        calls.append(watermark)
        return [], "de-catchup-next"

    monkeypatch.setattr(germany_runtime, "fetch_germany_doe_tenders", fake_fetch)
    first = germany_runtime.install()
    second = germany_runtime.install()
    rows = germany_runtime._app.fetch_base()

    assert first is second
    assert calls == ["de-old"]
    assert rows == [base]
    assert staged == [("SERVICE_BUND_DE", [], "de-catchup-next")]
    assert health[0][1]["success"] is True


def test_germany_runtime_stages_lifecycle_but_emits_only_actionable_rows(monkeypatch):
    staged = []
    monkeypatch.setattr(germany_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(germany_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(germany_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(germany_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    live = {"source": "SERVICE_BUND_DE", "external_id": "open", "is_actionable": True}
    closed = {
        "source": "SERVICE_BUND_DE",
        "external_id": "closed",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "awarded",
    }
    monkeypatch.setattr(germany_runtime, "fetch_germany_doe_tenders", lambda *, watermark=None: ([live, closed], "new"))

    germany_runtime.install()
    rows = germany_runtime._app.fetch_base()
    assert rows == [live]
    assert staged == [("SERVICE_BUND_DE", [live, closed], "new")]


def test_germany_runtime_failure_does_not_stage_or_advance_cursor(monkeypatch):
    staged, health = [], []
    base = {"source": "BASE", "external_id": "safe"}
    monkeypatch.setattr(germany_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(germany_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(germany_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(germany_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "de-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fail(*, watermark=None):
        assert watermark == "de-old"
        raise RuntimeError("daily ZIP invalid")

    monkeypatch.setattr(germany_runtime, "fetch_germany_doe_tenders", fail)
    germany_runtime.install()
    rows = germany_runtime._app.fetch_base()

    assert rows == [base]
    assert staged == []
    assert health and health[0][0] == "SERVICE_BUND_DE" and health[0][1]["success"] is False
