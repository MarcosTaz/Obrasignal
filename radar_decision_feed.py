"""Decision-aware radar feed helpers."""
from __future__ import annotations

from decision_log import latest_decision
from radar_decision_summary import summarize_decision


def enrich_rows(conn, rows):
    enriched = []
    for row in rows:
        item = dict(row)
        decision = latest_decision(conn, item.get("source"), item.get("external_id"))
        item["decision_summary"] = summarize_decision(decision)
        enriched.append(item)
    return enriched
