"""Temporary proof of exact LV IUB production bootstrap configuration; delete after success."""
from datetime import datetime, timezone

from official_json_bulk_adapter import DailyBulkCursor
from latvia_iub import build_iub_connector, fetch_iub_tenders


def test_lv_iub_exact_default_bootstrap_against_official_files():
    now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    connector = build_iub_connector()

    rows, cursor = fetch_iub_tenders(now=now, connector=connector)

    assert rows, "default IUB bootstrap returned no actionable tenders"
    assert DailyBulkCursor.decode(cursor).completed_through == "2026-08-23"
    # Default config must remain the audited production contract.
    assert connector.config.initial_lookback_days == 3
    assert connector.config.overlap_days == 1
    assert connector.config.max_days_per_sync == 7
    assert connector.config.publication_lag_days == 1
