"""TEMPORARY production smoke for Germany DOE. Delete before merge."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from germany_doe import GermanDOEOpenDataConnector


def test_germany_doe_production_live_smoke():
    connector = GermanDOEOpenDataConnector(
        initial_lookback_days=1,
        max_days_per_sync=2,
        overlap_days=0,
    )
    rows, cursor = connector.fetch_incremental(
        now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    )
    payload = json.loads(cursor)
    assert payload["completed_through"] == "2026-08-23"
    assert rows
    assert all(row.get("source") == "SERVICE_BUND_DE" for row in rows)
    assert all(row.get("contract_type") == "works" for row in rows)
    assert all(row.get("is_actionable") is True for row in rows)
    assert all(row.get("deadline") for row in rows)
    evidence = {
        "row_count": len(rows),
        "tracked_count": len(payload.get("tracked", {})),
        "closed_count": len(payload.get("closed", {})),
        "sample": [
            {
                "external_id": row.get("external_id"),
                "cpv": row.get("cpv"),
                "deadline": row.get("deadline"),
                "publication_date": row.get("publication_date"),
                "notice_identifier": row.get("notice_identifier"),
                "url": row.get("url"),
            }
            for row in rows[:8]
        ],
    }
    raise AssertionError(
        "GERMANY_DOE_PRODUCTION_SMOKE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000]
    )
