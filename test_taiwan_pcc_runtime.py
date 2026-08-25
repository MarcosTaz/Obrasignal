from taiwan_pcc_runtime import LIVE_SOURCES, fetch_incremental, install


class FakeConnector:
    created_sources = None

    def __init__(self, *args, **kwargs):
        type(self).created_sources = tuple(kwargs.get("sources") or ())

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


def test_runtime_live_slice_contains_pre_tender_and_contract_sources():
    assert [source.dataset_id for source in LIVE_SOURCES] == [7260, 7264]
    assert [source.signal_type for source in LIVE_SOURCES] == ["PROCUREMENT_PLAN", "CONTRACT"]
    assert all(source.url for source in LIVE_SOURCES)


def test_runtime_preserves_cursor_for_snapshot_ingestion(monkeypatch):
    monkeypatch.setattr("taiwan_pcc_runtime.TaiwanPCCPreparedConnector", FakeConnector)
    rows, cursor = fetch_incremental(watermark="opaque-existing-watermark", now="2026-08-25T00:00:00+00:00")
    assert len(rows) == 1
    assert cursor == "opaque-existing-watermark"
    assert rows[0]["source_reference"] == "A-1"
    assert [source.dataset_id for source in FakeConnector.created_sources] == [7260, 7264]


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
