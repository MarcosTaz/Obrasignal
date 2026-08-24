import incremental_runtime_plugin as runtime_plugin
import latvia_runtime
from source_registry import SOURCES, production_gate_reasons, production_ready_sources


class FakeConn:
    def close(self):
        pass


def test_lv_iub_registry_gate_is_ready_but_source_remains_explicit_opt_in(monkeypatch):
    assert SOURCES["LV_IUB"]["status"] == "ready"
    assert production_gate_reasons("LV_IUB") == ()
    assert "LV_IUB" in production_ready_sources()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert latvia_runtime._preload._global_source_enabled("LV_IUB") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "LV_IUB")
    assert latvia_runtime._preload._global_source_enabled("LV_IUB") is True


def test_lv_runtime_install_fetches_stages_and_is_idempotent(monkeypatch):
    staged = []
    health = []
    fetch_calls = []

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "LV_IUB")
    monkeypatch.setattr(latvia_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(latvia_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "lv-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(
        runtime_plugin,
        "record_source_result",
        lambda conn, source, **kwargs: health.append((source, kwargs)),
    )
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [{"source": "LV_IUB", "external_id": "procedure-1:lot:1"}], "lv-new"

    monkeypatch.setattr(latvia_runtime, "fetch_iub_tenders", fake_fetch)

    first = latvia_runtime.install()
    second = latvia_runtime.install()
    rows = latvia_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["lv-old"]
    assert [row["external_id"] for row in rows] == ["base-1", "procedure-1:lot:1"]
    assert staged == [("LV_IUB", [{"source": "LV_IUB", "external_id": "procedure-1:lot:1"}], "lv-new")]
    assert len(health) == 1
    assert health[0][0] == "LV_IUB"
    assert health[0][1]["success"] is True
