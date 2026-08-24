"""TEMPORARY: live production-connector smoke; delete after evidence."""
from datetime import datetime, timezone
import json

from estonia_rhr import EERHRCursor, EstoniaRHRConnector


def test_estonia_production_connector_live_current_month():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    connector = EstoniaRHRConnector(
        initial_months=1,
        overlap_months=0,
        max_months_per_sync=1,
        max_resource_bytes=80 * 1024 * 1024,
        timeout=180,
    )
    rows, cursor = connector.fetch_incremental(now=now)
    decoded = EERHRCursor.decode(cursor)
    active = [row for row in rows if row.get("is_actionable")]
    sample = [
        {
            "external_id": row.get("external_id"),
            "cpv": row.get("cpv"),
            "deadline": row.get("deadline"),
            "source_reference": row.get("source_reference"),
            "lot_id": row.get("lot_id"),
            "buyer_present": bool(row.get("buyer")),
            "url_present": bool(row.get("url")),
        }
        for row in active[:5]
    ]
    evidence = {
        "rows": len(rows),
        "active": len(active),
        "tracked": len(decoded.tracked),
        "periods": decoded.periods,
        "catchup_next": decoded.catchup_next,
        "sample": sample,
    }
    raise AssertionError("EE_RHR_PRODUCTION_LIVE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True))
