"""Temporary final live check for the exact production SERCOP connector.

Delete immediately after one successful run.
"""
from datetime import datetime, timezone

from ecuador_sercop import SERCOPBulkRecordConnector, SERCOP_LICENSE, build_sercop_connector
from ocds_bulk_adapter import OCDSMonthlyBulkCursor


def test_final_sercop_connector_contract_live():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    connector = build_sercop_connector(overlap_months=0)
    assert isinstance(connector, SERCOPBulkRecordConnector)

    observations, cursor = connector.fetch_incremental(now=now)
    assert observations
    for row in observations:
        assert row["source"] == "EC_SERCOP"
        assert row["country"] == "ECU"
        assert row["contract_type"] == "works"
        assert row["taxonomy"] == "CPC"
        assert row["cpv"] == ""
        assert row.get("category_code")
        assert row.get("license") == SERCOP_LICENSE
        assert "datosabiertos.compraspublicas.gob.ec/PLATAFORMA/ocds/" in row.get("url", "")
        if row["is_actionable"]:
            assert row["lifecycle_status"] == "active"
            deadline = datetime.fromisoformat(row["deadline"].replace("Z", "+00:00"))
            assert deadline.astimezone(timezone.utc) > now
        else:
            assert row.get("_lifecycle_only") is True

    decoded = OCDSMonthlyBulkCursor.decode(cursor)
    assert decoded is not None
    assert decoded.observed_through == "2026-08-24"
    assert decoded.periods == ("2026-08",)
    assert set(decoded.tracked_ocids) == {
        row["ocid"] for row in observations if row["is_actionable"]
    }
