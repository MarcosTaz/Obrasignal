import os

import pytest

from us_sam import fetch_us_sam_tenders


@pytest.mark.skipif(os.getenv("OBRASIGNAL_RUN_US_SAM_LIVE") != "1", reason="live SAM.gov gate is opt-in")
def test_live_sam_bulk_returns_real_federal_construction_opportunities():
    rows, cursor = fetch_us_sam_tenders()
    assert rows
    assert cursor
    assert all(row["source"] == "US_SAM" for row in rows)
    assert all(str(row.get("naics_code") or "").startswith("23") for row in rows)
    assert all(row.get("external_id") for row in rows)
    assert all(row.get("contract_type") == "works" for row in rows)
    assert all(row.get("value") == "" for row in rows)
