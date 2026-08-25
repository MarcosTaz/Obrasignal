import incremental_runtime_plugin as runtime_plugin
import netherlands_runtime


class FakeConn:
    def close(self):
        pass


def test_tenderned_runtime_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert netherlands_runtime._preload._global_source_enabled("NL_TENDERNED") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "NL_TENDERNED")
    assert netherlands_runtime._preload._global_source_enabled("NL_TENDERNED") is True


def test_tenderned_runtime_is_idempotent_and_persists_cursor(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    base = {"source": "BASE", "external_id": "base-1"}
    monkeypatch.setattr(netherlands_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(netherlands_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(netherlands_runtime._preload, "_global_source_enabled", lambda source: source == "NL_TENDERNED")
    monkeypatch.setattr(netherlands_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "nl-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [], "nl-new"

    monkeypatch.setattr(netherlands_runtime, "fetch_tenderned_tenders", fake_fetch)
    first = netherlands_runtime.install()
    second = netherlands_runtime.install()
    rows = netherlands_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["nl-old"]
    assert rows == [base]
    assert staged == [("NL_TENDERNED", [], "nl-new")]
    assert health[0][1]["success"] is True


def test_tenderned_runtime_stages_lifecycle_but_emits_only_open_rows(monkeypatch):
    staged = []
    monkeypatch.setattr(netherlands_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(netherlands_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(netherlands_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(netherlands_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    live = {"source": "NL_TENDERNED", "external_id": "open-1", "is_actionable": True}
    closed = {
        "source": "NL_TENDERNED",
        "external_id": "closed-1",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "awarded",
    }
    monkeypatch.setattr(
        netherlands_runtime,
        "fetch_tenderned_tenders",
        lambda *, watermark=None: ([live, closed], "new"),
    )

    netherlands_runtime.install()
    rows = netherlands_runtime._app.fetch_base()
    assert rows == [live]
    assert staged == [("NL_TENDERNED", [live, closed], "new")]


def test_tenderned_runtime_failure_does_not_stage_or_advance_cursor(monkeypatch):
    staged = []
    health = []
    base = {"source": "BASE", "external_id": "base-safe"}
    monkeypatch.setattr(netherlands_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(netherlands_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(netherlands_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(netherlands_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "nl-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fail(*, watermark=None):
        assert watermark == "nl-old"
        raise RuntimeError("pagination snapshot changed")

    monkeypatch.setattr(netherlands_runtime, "fetch_tenderned_tenders", fail)
    netherlands_runtime.install()
    rows = netherlands_runtime._app.fetch_base()

    assert rows == [base]
    assert staged == []
    assert health and health[0][0] == "NL_TENDERNED"
    assert health[0][1]["success"] is False
