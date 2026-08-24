import os

import pytest

from canada_buys import CanadaBuysConnector


@pytest.mark.skipif(os.getenv("OBRASIGNAL_LIVE_CANADABUYS") != "1", reason="live CanadaBuys smoke is opt-in")
def test_live_canadabuys_production_path_returns_cursor_and_only_construction():
    rows, cursor = CanadaBuysConnector().fetch_incremental(watermark=None)
    assert isinstance(cursor, str) and cursor
    assert rows
    assert all(row["source"] == "CA_CANADABUYS" for row in rows)
    assert all("CNST" in row.get("procurement_categories", []) for row in rows)
    assert all(row.get("external_id") for row in rows)
