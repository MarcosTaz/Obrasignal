import estonia_runtime
import incremental_runtime_plugin as runtime_plugin
from source_registry import SOURCES, production_gate_reasons


class FakeConn:
    def close(self):
        pass


def test_estonia_ready_still_requires_explicit_runtime_opt_in(monkeypatch):
    assert SOURCES["EE_RHR"]["status"] == "ready"
    assert production_gate_reasons("EE_RHR") == ()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert estonia_runtime._preload._global_source_enabled("EE_RHR") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "EE_RHR")
    assert estonia_runtime._preload._global_source_enabled("EE_RHR") is True


def test_estonia_runtime_stages_lifecycle_but_emits_only_live_rows(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    monkeypatch.setattr(estonia_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(estonia_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(estonia_runtime._preload, "_global_source_enabled", lambda source: source == "EE_RHR")
    monkeypatch.setattr(estonia_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "ee-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    live = {
        "source": "EE_RHR",
        "external_id": "folder-1::LOT-0000",
        "is_actionable": True,
        "contract_type": "works",
    }
    closed = {
        "source": "EE_RHR",
        "external_id": "folder-2::LOT-0000",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "result_published",
    }

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [live, closed], "ee-new"

    monkeypatch.setattr(estonia_runtime, "fetch_estonia_rhr_tenders", fake_fetch)

    first = estonia_runtime.install()
    second = estonia_runtime.install()
    rows = estonia_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["ee-old"]
    assert [row["external_id"] for row in rows] == ["base-1", "folder-1::LOT-0000"]
    assert staged == [("EE_RHR", [live, closed], "ee-new")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 2
