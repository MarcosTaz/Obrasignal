"""Temporary integrated live proof for permanent LV IUB connector; delete after one successful run."""
from datetime import datetime, timezone

from official_json_bulk_adapter import DailyBulkCursor
from latvia_iub import LV_IUB_LICENSE, build_iub_connector, fetch_iub_tenders


def test_permanent_lv_iub_connector_against_official_daily_json():
    now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    connector = build_iub_connector()
    connector.config = type(connector.config)(
        **{
            **connector.config.__dict__,
            "initial_lookback_days": 0,
            "overlap_days": 0,
            "max_days_per_sync": 1,
        }
    )

    rows, cursor = fetch_iub_tenders(now=now, connector=connector)

    assert rows, "official IUB 2026-08-23 daily JSON returned no actionable future competition lots"
    parsed = DailyBulkCursor.decode(cursor)
    assert parsed is not None
    assert parsed.completed_through == "2026-08-23"
    for row in rows[:20]:
        assert row["source"] == "LV_IUB"
        assert row["country"] == "LVA"
        assert row["signal_type"] == "TENDER"
        assert row["external_id"]
        assert row["procurement_procedure_identifier"]
        assert row["lot_sequence"]
        assert row["deadline"]
        deadline = datetime.fromisoformat(row["deadline"].replace("Z", "+00:00"))
        assert deadline > now
        assert row["license"] == LV_IUB_LICENSE
        assert row["currency"] == ""
