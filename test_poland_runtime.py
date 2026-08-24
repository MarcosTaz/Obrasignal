import poland_runtime
import incremental_runtime_plugin as runtime_plugin
from source_registry import SOURCES, production_gate_reasons


class FakeConn:
    def close(self):
        pass


def test_bzp_ready_still_requires_explicit_runtime_opt_in(monkeypatch):
    assert SOURCES["PL_BZP"]["status"] == "ready"
    assert production_gate_reasons("PL_BZP") == ()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert poland_runtime._preload._global_source_enabled("PL_BZP") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "PL_BZP")
    assert poland_runtime._preload._global_source_enabled("PL_BZP") is True


def test_bzp_runtime_stages_lifecycle_but_emits_only_live_rows(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    monkeypatch.setattr(poland_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(poland_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(poland_runtime._preload, "_global_source_enabled", lambda source: source == "PL_BZP")
    monkeypatch.setattr(poland_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "pl-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    live = {
        "source": "PL_BZP",
        "external_id": "ocds-148610-work-1",
        "is_actionable": True,
        "contract_type": "works",
    }
    closed = {
        "source": "PL_BZP",
        "external_id": "ocds-148610-work-2",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "contract_concluded",
    }

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [live, closed], "pl-new"

    monkeypatch.setattr(poland_runtime, "fetch_poland_bzp_tenders", fake_fetch)

    first = poland_runtime.install()
    second = poland_runtime.install()
    rows = poland_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["pl-old"]
    assert [row["external_id"] for row in rows] == ["base-1", "ocds-148610-work-1"]
    assert staged == [("PL_BZP", [live, closed], "pl-new")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 2
