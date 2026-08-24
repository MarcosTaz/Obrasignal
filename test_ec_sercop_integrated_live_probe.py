"""Temporary live validation for the permanent Ecuador SERCOP connector.

Delete after one successful run; permanent CI must remain offline.
"""
from datetime import datetime, timezone

from ecuador_sercop import SERCOP_LICENSE, build_sercop_connector
from ocds_bulk_adapter import OCDSMonthlyBulkCursor


def test_permanent_sercop_connector_against_current_official_output():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    connector = build_sercop_connector(overlap_months=0)
    observations, cursor = connector.fetch_incremental(now=now)

    assert observations
    assert all(row["source"] == "EC_SERCOP" for row in observations)
    assert all(row["country"] == "ECU" for row in observations)
    assert all(row["contract_type"] == "works" for row in observations)
    assert all(row["taxonomy"] == "CPC" for row in observations)
    assert all(row["cpv"] == "" for row in observations)
    assert all(row.get("category_code") for row in observations)
    assert all("is_actionable" in row for row in observations)
    assert all(row.get("license") == SERCOP_LICENSE for row in observations)
    assert all("datosabiertos.compraspublicas.gob.ec/PLATAFORMA/ocds/" in row.get("url", "") for row in observations)
    assert all(row.get("currency") in ("", "USD") for row in observations)

    for row in observations:
        if row["is_actionable"]:
            assert row["lifecycle_status"] == "active"
            assert not row.get("_lifecycle_only")
            deadline = datetime.fromisoformat(row["deadline"].replace("Z", "+00:00"))
            assert deadline.astimezone(timezone.utc) > now
        else:
            assert row.get("_lifecycle_only") is True
            assert row.get("lifecycle_status") in {"complete", "cancelled", "unsuccessful", "withdrawn", "deadline_expired", "deadline_missing", "inactive"}

    decoded = OCDSMonthlyBulkCursor.decode(cursor)
    assert decoded is not None
    assert decoded.observed_through == "2026-08-24"
    assert decoded.periods == ("2026-08",)
