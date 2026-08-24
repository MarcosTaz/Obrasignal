import incremental_runtime_plugin as runtime_plugin
import uk_runtime
from source_registry import SOURCES, production_gate_reasons


class FakeConn:
    def close(self):
        pass


def test_uk_registry_remains_planned_and_env_cannot_bypass_gate(monkeypatch):
    assert SOURCES["UK_PROCUREMENT"]["status"] == "planned"
    assert "runtime_not_enabled" in production_gate_reasons("UK_PROCUREMENT")
    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "UK_PROCUREMENT")
    assert uk_runtime._preload._global_source_enabled("UK_PROCUREMENT") is False


def test_uk_runtime_uses_generic_staging_path_when_gate_is_opened_in_test(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    monkeypatch.setattr(uk_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(uk_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(uk_runtime._preload, "_global_source_enabled", lambda source: source == "UK_PROCUREMENT")
    monkeypatch.setattr(uk_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "uk-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    live = {"source": "UK_PROCUREMENT", "external_id": "ocid:lot:1", "is_actionable": True}
    closed = {
        "source": "UK_PROCUREMENT",
        "external_id": "ocid:lot:2",
        "is_actionable": False,
        "_lifecycle_only": True,
    }

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [live, closed], "uk-new"

    monkeypatch.setattr(uk_runtime, "fetch_uk_tenders", fake_fetch)

    first = uk_runtime.install()
    second = uk_runtime.install()
    rows = uk_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["uk-old"]
    assert [row["external_id"] for row in rows] == ["base-1", "ocid:lot:1"]
    assert staged == [("UK_PROCUREMENT", [live, closed], "uk-new")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 2
