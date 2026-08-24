import incremental_runtime_plugin as runtime_plugin
import korea_runtime


class FakeConn:
    def close(self):
        pass


def test_korea_runtime_remains_blocked_by_registry_even_with_env_opt_in(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "KR_KONEPS")
    assert korea_runtime._preload._global_source_enabled("KR_KONEPS") is False


def test_korea_runtime_is_idempotent_when_gate_is_later_enabled(monkeypatch):
    staged, health, calls = [], [], []
    base = {"source": "BASE", "external_id": "base-1"}
    monkeypatch.setattr(korea_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(korea_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(korea_runtime._preload, "_global_source_enabled", lambda source: source == "KR_KONEPS")
    monkeypatch.setattr(korea_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "kr-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        calls.append(watermark)
        return [], "kr-next"

    monkeypatch.setattr(korea_runtime, "fetch_korea_koneps_tenders", fake_fetch)
    first = korea_runtime.install()
    second = korea_runtime.install()
    rows = korea_runtime._app.fetch_base()

    assert first is second
    assert calls == ["kr-old"]
    assert rows == [base]
    assert staged == [("KR_KONEPS", [], "kr-next")]
    assert health[0][1]["success"] is True


def test_korea_runtime_stages_lifecycle_but_emits_only_actionable_rows(monkeypatch):
    staged = []
    monkeypatch.setattr(korea_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(korea_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(korea_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(korea_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    live = {"source": "KR_KONEPS", "external_id": "R26BK1", "is_actionable": True}
    closed = {
        "source": "KR_KONEPS",
        "external_id": "R26BK2",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "publisher_cancelled",
    }
    monkeypatch.setattr(korea_runtime, "fetch_korea_koneps_tenders", lambda *, watermark=None: ([live, closed], "new"))

    korea_runtime.install()
    rows = korea_runtime._app.fetch_base()
    assert rows == [live]
    assert staged == [("KR_KONEPS", [live, closed], "new")]


def test_korea_runtime_failure_does_not_stage_or_advance_cursor(monkeypatch):
    staged, health = [], []
    base = {"source": "BASE", "external_id": "safe"}
    monkeypatch.setattr(korea_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(korea_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(korea_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(korea_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "kr-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fail(*, watermark=None):
        assert watermark == "kr-old"
        raise RuntimeError("KONEPS API service key rejected")

    monkeypatch.setattr(korea_runtime, "fetch_korea_koneps_tenders", fail)
    korea_runtime.install()
    rows = korea_runtime._app.fetch_base()

    assert rows == [base]
    assert staged == []
    assert health and health[0][0] == "KR_KONEPS" and health[0][1]["success"] is False
