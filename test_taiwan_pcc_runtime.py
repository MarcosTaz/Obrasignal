from taiwan_pcc_runtime import fetch_incremental


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
