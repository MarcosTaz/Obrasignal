import austria_runtime
import incremental_runtime_plugin as runtime_plugin
from source_registry import SOURCES, production_gate_reasons


class FakeConn:
    def close(self):
        pass


def test_austria_ready_still_requires_explicit_runtime_opt_in(monkeypatch):
    assert SOURCES["AT_KERNDATEN"]["status"] == "ready"
    assert production_gate_reasons("AT_KERNDATEN") == ()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert austria_runtime._preload._global_source_enabled("AT_KERNDATEN") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "AT_KERNDATEN")
    assert austria_runtime._preload._global_source_enabled("AT_KERNDATEN") is True


def test_austria_runtime_stages_catchup_cursor_even_with_zero_commercial_rows(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    monkeypatch.setattr(austria_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(austria_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(austria_runtime._preload, "_global_source_enabled", lambda source: source == "AT_KERNDATEN")
    monkeypatch.setattr(austria_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "at-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        # A partial national catch-up intentionally emits no opportunities but
        # must persist its new cursor so the next worker run resumes progress.
        return [], "at-catchup-next"

    monkeypatch.setattr(austria_runtime, "fetch_austria_kerndaten_tenders", fake_fetch)

    first = austria_runtime.install()
    second = austria_runtime.install()
    rows = austria_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["at-old"]
    assert rows == [{"source": "BASE", "external_id": "base-1"}]
    assert staged == [("AT_KERNDATEN", [], "at-catchup-next")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 0


def test_austria_runtime_stages_lifecycle_but_emits_only_open_rows(monkeypatch):
    staged = []
    monkeypatch.setattr(austria_runtime._app, "fetch_base", lambda: [])
    monkeypatch.setattr(austria_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(austria_runtime._preload, "_global_source_enabled", lambda source: True)
    monkeypatch.setattr(austria_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old")
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))

    live = {"source": "AT_KERNDATEN", "external_id": "open-1", "is_actionable": True}
    closed = {
        "source": "AT_KERNDATEN",
        "external_id": "closed-1",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "deadline_elapsed",
    }
    monkeypatch.setattr(
        austria_runtime,
        "fetch_austria_kerndaten_tenders",
        lambda *, watermark=None: ([live, closed], "new"),
    )

    austria_runtime.install()
    rows = austria_runtime._app.fetch_base()
    assert rows == [live]
    assert staged == [("AT_KERNDATEN", [live, closed], "new")]
