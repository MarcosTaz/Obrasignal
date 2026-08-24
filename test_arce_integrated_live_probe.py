"""Temporary integrated live validation for UY_ARCE; delete after one result."""
from datetime import timedelta

from uruguay_arce import (
    ARCECursor,
    ARCEOCDSRSSAdapter,
    ARCE_RSS_URL,
    _parse_iso,
    monthly_rss_url,
    parse_arce_rss,
)


def test_arce_permanent_adapter_against_official_live_source():
    client = ARCEOCDSRSSAdapter(
        initial_lookback_hours=24,
        overlap_seconds=2,
        max_events_per_sync=5,
        max_release_refs_per_process=50,
    )
    live_events = client._feed(ARCE_RSS_URL)
    tender_events = [
        event for event in live_events
        if str(event.category or "").lower().startswith("tender") and event.purchase_id
    ]
    assert tender_events, "official ARCE current RSS contained no tender event to validate"

    target = tender_events[-1]
    target_dt = _parse_iso(target.published_at)
    watermark = ARCECursor(
        (target_dt - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "live-probe-before-target",
    ).encode()

    rows, cursor = client.fetch_incremental(watermark=watermark, now=target_dt + timedelta(days=2))
    parsed_cursor = ARCECursor.decode(cursor)
    assert parsed_cursor is not None
    assert _parse_iso(parsed_cursor.published_at) >= target_dt
    for row in rows:
        assert row["source"] == "UY_ARCE"
        assert row["country"] == "URY"
        assert row["signal_type"] == "TENDER"
        assert row["external_id"].startswith("ocds-yfs5dr-")
        assert _parse_iso(row["deadline"]) > target_dt + timedelta(days=2)
        assert row["license"]
        assert row["attribution"]

    monthly_url = monthly_rss_url(target_dt)
    monthly_events = client._feed(monthly_url)
    assert monthly_events, monthly_url
    assert all(event.guid for event in monthly_events[:10])
