"""TEMPORARY live production smoke for AT_KERNDATEN.

Delete before merge. It measures the 60-day first-sync envelope without fetching
all notices, then runs the real connector end-to-end over a bounded 3-day window.
The final assertion is deliberate so CI preserves the evidence in logs.
"""
from datetime import datetime, timedelta, timezone
import json

from austria_kerndaten import (
    AustriaKerndatenConnector,
    AustriaKerndatenCursor,
    _parse_notice,
    _parse_source_datetime,
)


def test_austria_production_connector_live_smoke():
    now = datetime.now(timezone.utc)
    measure = AustriaKerndatenConnector()
    cursor = AustriaKerndatenCursor.empty()
    datasets = measure._discover(cursor)

    evidence = {
        "at": now.isoformat(),
        "dataset_count": len(datasets),
        "kdqs": [],
        "sixty_day_max_selected": 0,
        "sample_actionable_rows": 0,
    }
    cutoff = now - timedelta(days=60)
    accessible = 0
    for dataset_id, entry in datasets.items():
        for kdq_url in list((entry or {}).get("urls") or []):
            row = {"dataset_id": dataset_id, "kdq_url": kdq_url}
            try:
                items = measure._kdq_items(kdq_url)
                accessible += 1
                selected = [
                    item for item in items
                    if (_parse_source_datetime(item.get("lastmod")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
                ]
                row["item_count"] = len(items)
                row["selected_60d"] = len(selected)
                evidence["sixty_day_max_selected"] = max(evidence["sixty_day_max_selected"], len(selected))
                roots = []
                actionable = 0
                for item in selected[:2]:
                    payload = measure._notice_payload(item["url"])
                    states = _parse_notice(
                        payload,
                        dataset_id=dataset_id,
                        item_id=item["id"],
                        item_lastmod=item["lastmod"],
                        notice_url=item["url"],
                    )
                    if states:
                        actionable += len(states)
                        roots.extend(sorted({state.get("root_family") for state in states if state.get("root_family")}))
                row["sample_actionable"] = actionable
                row["sample_roots"] = roots
                evidence["sample_actionable_rows"] += actionable
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
            evidence["kdqs"].append(row)

    evidence["accessible_kdqs"] = accessible
    assert accessible > 0
    assert evidence["sixty_day_max_selected"] <= measure.max_notice_fetches_per_kdq

    # Real end-to-end production code path with a bounded initial window.
    smoke = AustriaKerndatenConnector(initial_lookback_days=3)
    observations, next_cursor = smoke.fetch_incremental(now=now)
    decoded = AustriaKerndatenCursor.decode(next_cursor)
    evidence["end_to_end"] = {
        "observations": len(observations),
        "actionable": sum(1 for row in observations if row.get("is_actionable")),
        "tracked": len(decoded.tracked),
        "datasets": len(decoded.datasets),
        "kdq_watermarks": len(decoded.kdq_observed),
        "sample": [
            {
                "external_id": row.get("external_id"),
                "title": row.get("title"),
                "cpv": row.get("cpv"),
                "deadline": row.get("deadline"),
                "buyer": row.get("buyer"),
                "payload_family": row.get("payload_family"),
            }
            for row in observations[:5]
        ],
    }

    raise AssertionError(
        "AT_KERNDATEN_PRODUCTION_SMOKE_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000]
    )
