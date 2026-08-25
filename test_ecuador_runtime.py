import ecuador_runtime
import incremental_runtime_plugin as runtime_plugin
from source_registry import SOURCES, production_gate_reasons


class FakeConn:
    def close(self):
        pass


def test_ecuador_ready_still_requires_explicit_runtime_opt_in(monkeypatch):
    assert SOURCES["EC_SERCOP"]["status"] == "ready"
    assert production_gate_reasons("EC_SERCOP") == ()

    monkeypatch.delenv("OBRASIGNAL_GLOBAL_SOURCES", raising=False)
    assert ecuador_runtime._preload._global_source_enabled("EC_SERCOP") is False

    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "EC_SERCOP")
    assert ecuador_runtime._preload._global_source_enabled("EC_SERCOP") is True


def test_ecuador_runtime_stages_tombstones_but_emits_only_live_rows(monkeypatch):
    staged = []
    health = []
    fetch_calls = []
    monkeypatch.setattr(ecuador_runtime._app, "fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(ecuador_runtime._app, "db", lambda: FakeConn())
    monkeypatch.setattr(ecuador_runtime._preload, "_global_source_enabled", lambda source: source == "EC_SERCOP")
    monkeypatch.setattr(ecuador_runtime._preload, "_record_blocked_global_source", lambda source: None)
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "ec-old")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda conn, source, **kwargs: health.append((source, kwargs)))
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    live = {
        "source": "EC_SERCOP",
        "external_id": "ocds-live",
        "is_actionable": True,
        "contract_type": "works",
    }
    expired = {
        "source": "EC_SERCOP",
        "external_id": "ocds-expired",
        "is_actionable": False,
        "_lifecycle_only": True,
        "lifecycle_status": "deadline_expired",
    }

    def fake_fetch(*, watermark=None):
        fetch_calls.append(watermark)
        return [live, expired], "ec-new"

    monkeypatch.setattr(ecuador_runtime, "fetch_sercop_tenders", fake_fetch)

    first = ecuador_runtime.install()
    second = ecuador_runtime.install()
    rows = ecuador_runtime._app.fetch_base()

    assert first is second
    assert fetch_calls == ["ec-old"]
    assert [row["external_id"] for row in rows] == ["base-1", "ocds-live"]
    assert staged == [("EC_SERCOP", [live, expired], "ec-new")]
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 2
