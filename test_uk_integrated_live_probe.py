"""Temporary integrated proof for permanent UK connector; delete after one successful run."""
from datetime import datetime, timezone

from ocds_cursor_adapter import OCDSOpaqueWindowCursor
from uk_find_tender import FTS_LICENSE, UKFindTenderConnector


def test_permanent_uk_connector_against_current_find_tender_output():
    connector = UKFindTenderConnector()
    connector.transport.config = type(connector.transport.config)(
        **{
            **connector.transport.config.__dict__,
            "initial_lookback_minutes": 15,
            "max_windows_per_sync": 1,
            "overlap_minutes": 0,
        }
    )
    # 080242-2026 / ocds-h6vhtk-06ea4b was published at 10:13:05 UTC.
    now = datetime(2026, 8, 24, 10, 20, tzinfo=timezone.utc)
    observations, cursor = connector.fetch_incremental(now=now)

    swansea = [row for row in observations if row.get("ocid") == "ocds-h6vhtk-06ea4b"]
    assert len(swansea) == 2
    assert {row["external_id"] for row in swansea} == {
        "ocds-h6vhtk-06ea4b:lot:1",
        "ocds-h6vhtk-06ea4b:lot:2",
    }
    assert all(row["is_actionable"] is True for row in swansea)
    assert all(row["contract_type"] == "works" for row in swansea)
    assert all(row["currency"] == "GBP" for row in swansea)
    assert all(row["deadline"] == "2026-09-21T12:00:00+01:00" for row in swansea)
    assert all(row["license"] == FTS_LICENSE for row in swansea)
    assert all(row["cpv"] for row in swansea)
    assert OCDSOpaqueWindowCursor.decode(cursor).completed_through == "2026-08-24T10:20:00Z"
