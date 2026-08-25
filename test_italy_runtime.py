import incremental_runtime_plugin as runtime_plugin
import italy_runtime


class FakeConn:
    def close(self):
        pass


def test_italy_runtime_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert italy_runtime._preload._global_source_enabled("IT_ANAC") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "IT_ANAC")
    assert italy_runtime._preload._global_source_enabled("IT_ANAC") is True


def test_italy_runtime_is_idempotent_and_persists_cursor(monkeypatch):
    staged, health, calls = [], [], []
    base = {"source": "BASE", "external_id": "base-1"}
    monkeypatch.setattr(italy_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(italy_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(italy_runtime._preload, "_global_source_enabled", lambda source: source == "IT_ANAC")
    monkeypatch.setattr(italy_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "it-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        calls.append(watermark)
        return [], "it-next"

    monkeypatch.setattr(italy_runtime, "fetch_italy_anac_tenders", fake_fetch)
    first = italy_runtime.install()
    second = italy_runtime.install()
    rows = italy_runtime._app.fetch_base()

    assert first is second
    assert calls == ["it-old"]
    assert rows == [base]
    assert staged == [("IT_ANAC", [], "it-next")]
    assert health[0][1]["success"] is True


def test_italy_runtime_stages_lifecycle_but_emits_only_actionable_rows(monkeypatch):
    staged = []
    monkeypatch.setattr(italy_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(italy_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(italy_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(italy_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    live = {"source": "IT_ANAC", "external_id": "CIG-OPEN", "is_actionable": True}
    closed = {
        "source": "IT_ANAC",
        "external_id": "CIG-CLOSED",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "publisher_inactive",
    }
    monkeypatch.setattr(italy_runtime, "fetch_italy_anac_tenders", lambda *, watermark=None: ([live, closed], "new"))

    italy_runtime.install()
    rows = italy_runtime._app.fetch_base()
    assert rows == [live]
    assert staged == [("IT_ANAC", [live, closed], "new")]


def test_italy_runtime_failure_does_not_stage_or_advance_cursor(monkeypatch):
    staged, health = [], []
    base = {"source": "BASE", "external_id": "safe"}
    monkeypatch.setattr(italy_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(italy_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(italy_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(italy_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "it-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fail(*, watermark=None):
        assert watermark == "it-old"
        raise RuntimeError("PVL pagination changed")

    monkeypatch.setattr(italy_runtime, "fetch_italy_anac_tenders", fail)
    italy_runtime.install()
    rows = italy_runtime._app.fetch_base()

    assert rows == [base]
    assert staged == []
    assert health and health[0][0] == "IT_ANAC" and health[0][1]["success"] is False
