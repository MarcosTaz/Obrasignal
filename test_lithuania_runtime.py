import incremental_runtime_plugin as runtime_plugin
import lithuania_runtime


class FakeConn:
    def close(self):
        pass


def test_lithuania_runtime_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert lithuania_runtime._preload._global_source_enabled("LT_VPT") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "LT_VPT")
    assert lithuania_runtime._preload._global_source_enabled("LT_VPT") is True


def test_lithuania_runtime_persists_complete_snapshot_cursor_with_zero_changes(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    base = {"source": "BASE", "external_id": "base-1"}
    monkeypatch.setattr(lithuania_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(lithuania_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(lithuania_runtime._preload, "_global_source_enabled", lambda source: source == "LT_VPT")
    monkeypatch.setattr(lithuania_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "lt-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [], "lt-snapshot-complete"

    monkeypatch.setattr(lithuania_runtime, "fetch_lithuania_vpt_tenders", fake_fetch)

    first = lithuania_runtime.install()
    second = lithuania_runtime.install()
    rows = lithuania_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["lt-old"]
    assert rows == [base]
    assert staged == [("LT_VPT", [], "lt-snapshot-complete")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 0


def test_lithuania_runtime_stages_lifecycle_but_emits_only_open_rows(monkeypatch):
    staged = []
    monkeypatch.setattr(lithuania_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(lithuania_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(lithuania_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(lithuania_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    live = {"source": "LT_VPT", "external_id": "open-1", "is_actionable": True}
    closed = {
        "source": "LT_VPT",
        "external_id": "closed-1",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "awarded",
    }
    monkeypatch.setattr(
        lithuania_runtime,
        "fetch_lithuania_vpt_tenders",
        lambda *, watermark=None: ([live, closed], "new"),
    )

    lithuania_runtime.install()
    rows = lithuania_runtime._app.fetch_base()
    assert rows == [live]
    assert staged == [("LT_VPT", [live, closed], "new")]


def test_lithuania_runtime_failure_does_not_stage_or_advance_cursor(monkeypatch):
    staged = []
    health = []
    base = {"source": "BASE", "external_id": "base-safe"}
    monkeypatch.setattr(lithuania_runtime._app, "fetch_base", lambda: [base])
    monkeypatch.setattr(lithuania_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(lithuania_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(lithuania_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "lt-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fail(*, watermark=None):
        assert watermark == "lt-old"
        raise RuntimeError("snapshot incomplete")

    monkeypatch.setattr(lithuania_runtime, "fetch_lithuania_vpt_tenders", fail)

    lithuania_runtime.install()
    rows = lithuania_runtime._app.fetch_base()

    assert rows == [base]
    assert staged == []
    assert health and health[0][0] == "LT_VPT"
    assert health[0][1]["success"] is False
