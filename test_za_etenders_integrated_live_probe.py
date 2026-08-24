"""Temporary integrated live proof for permanent ZA connector; delete after one result."""
from datetime import datetime, timezone

from ocds_adapter import OCDSWindowCursor
from south_africa_etenders import ZA_ETENDERS_LICENSE, build_za_connector, fetch_za_tenders


def test_permanent_za_connector_against_official_live_api():
    now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    connector = build_za_connector()
    connector.config = type(connector.config)(
        **{
            **connector.config.__dict__,
            "overlap_days": 0,
            "max_windows_per_sync": 1,
        }
    )
    watermark = OCDSWindowCursor("2026-08-23").encode()

    rows, cursor = fetch_za_tenders(watermark=watermark, now=now, connector=connector)

    assert rows, "official ZA eTenders day window returned no actionable active/future tender"
    parsed_cursor = OCDSWindowCursor.decode(cursor)
    assert parsed_cursor is not None
    assert parsed_cursor.completed_through == "2026-08-24"
    for row in rows[:10]:
        assert row["source"] == "ZA_ETENDERS"
        assert row["country"] == "ZAF"
        assert str(row["external_id"]).startswith("ocds-9t57fa-")
        deadline = datetime.fromisoformat(str(row["deadline"]).replace("Z", "+00:00"))
        assert deadline > now
        assert row["license"] == ZA_ETENDERS_LICENSE
        assert row["attribution"]
        assert row["coverage_note"]
