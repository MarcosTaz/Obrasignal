"""TEMPORARY forensic probe; remove after measuring daily OCDS discovery volume."""
from datetime import datetime, timedelta, timezone
import json

import requests

from dominican_republic_dgcp import DGCP_OCDS_RELEASES_URL


def test_temporary_dgcp_daily_ocds_volume_probe():
    today = datetime.now(timezone.utc).date()
    counts = {}
    for days_ago in range(1, 15):
        day = today - timedelta(days=days_ago)
        response = requests.get(
            DGCP_OCDS_RELEASES_URL,
            params={
                "page": 1,
                "limit": 1,
                "start_date": day.isoformat(),
                "end_date": day.isoformat(),
            },
            headers={"Accept": "application/json", "User-Agent": "ObraSignal temporary promotion probe/1.0"},
            timeout=45,
        )
        response.raise_for_status()
        envelope = response.json()
        if not isinstance(envelope, dict) or envelope.get("hasError") is not False or envelope.get("code") != 200:
            raise RuntimeError(f"unexpected DGCP envelope for {day}")
        total = envelope.get("totalResults")
        pages = envelope.get("pages")
        counts[day.isoformat()] = {"totalResults": total, "pages_at_limit_1": pages}
    totals = [int(item["totalResults"] or 0) for item in counts.values()]
    summary = {
        "days": counts,
        "max_total": max(totals) if totals else 0,
        "mean_total": round(sum(totals) / len(totals), 2) if totals else 0,
        "days_above_250": sum(total > 250 for total in totals),
    }
    raise AssertionError("DGCP_OCDS_DAILY_VOLUME=" + json.dumps(summary, sort_keys=True))
