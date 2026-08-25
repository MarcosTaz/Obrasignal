from taiwan_pcc_runtime import fetch_incremental, install


class FakeConnector:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_snapshot(self, *, observed_at=None):
        return [
            {
                "source": "TW_PCC",
                "signal_type": "PROCUREMENT_PLAN",
                "external_id": "procurement_plan:A-1",
                "source_reference": "A-1",
                "lineage_key": "A-1",
            }
        ]


def test_runtime_preserves_cursor_for_rolling_snapshot(monkeypatch):
    monkeypatch.setattr("taiwan_pcc_runtime.TaiwanPCCPreparedConnector", FakeConnector)
    rows, cursor = fetch_incremental(watermark="opaque-existing-watermark", now="2026-08-25T00:00:00+00:00")
    assert len(rows) == 1
    assert cursor == "opaque-existing-watermark"
    assert rows[0]["source_reference"] == "A-1"


def test_runtime_install_uses_generic_incremental_plugin(monkeypatch):
    calls = []

    def fake_install(app_module, **kwargs):
        calls.append((app_module, kwargs))
        return "installed"

    monkeypatch.setattr("taiwan_pcc_runtime.install_incremental_source", fake_install)
    app_module = object()
    source_enabled = lambda source: True
    record_blocked = lambda source: None

    assert install(app_module, source_enabled=source_enabled, record_blocked=record_blocked) == "installed"
    assert len(calls) == 1
    called_app, kwargs = calls[0]
    assert called_app is app_module
    assert kwargs["source"] == "TW_PCC"
    assert kwargs["fetch_incremental"] is fetch_incremental
    assert kwargs["source_enabled"] is source_enabled
    assert kwargs["record_blocked"] is record_blocked
