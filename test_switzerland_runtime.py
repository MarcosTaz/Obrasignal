import switzerland_runtime
import incremental_runtime_plugin as runtime_plugin
from source_registry import SOURCES, production_gate_reasons


class FakeConn:
    def close(self):
        pass


def test_simap_ready_still_requires_explicit_runtime_opt_in(monkeypatch):
    assert SOURCES["CH_SIMAP"]["status"] == "ready"
    assert production_gate_reasons("CH_SIMAP") == ()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert switzerland_runtime._preload._global_source_enabled("CH_SIMAP") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "CH_SIMAP")
    assert switzerland_runtime._preload._global_source_enabled("CH_SIMAP") is True


def test_simap_runtime_stages_tombstones_but_emits_only_live_rows(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    monkeypatch.setattr(switzerland_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(switzerland_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(switzerland_runtime._preload, "_global_source_enabled", lambda source: source == "CH_SIMAP")
    monkeypatch.setattr(switzerland_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "ch-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    live = {
        "source": "CH_SIMAP",
        "external_id": "project-1:lot:lot-1",
        "is_actionable": True,
        "contract_type": "execution",
    }
    revoked = {
        "source": "CH_SIMAP",
        "external_id": "project-2",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "revoked",
    }

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [live, revoked], "ch-new"

    monkeypatch.setattr(switzerland_runtime, "fetch_simap_tenders", fake_fetch)

    first = switzerland_runtime.install()
    second = switzerland_runtime.install()
    rows = switzerland_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["ch-old"]
    assert [row["external_id"] for row in rows] == ["base-1", "project-1:lot:lot-1"]
    assert staged == [("CH_SIMAP", [live, revoked], "ch-new")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 2
