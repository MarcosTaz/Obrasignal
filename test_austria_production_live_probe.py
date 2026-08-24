"""TEMPORARY bounded live transport smoke for AT_KERNDATEN.

Delete before merge. Measure the real 60-day first-sync envelope from KDQ
indexes and parse only a few real notices. The final failure preserves evidence.
"""
from datetime import datetime, timedelta, timezone
import json

from austria_kerndaten import (
    AustriaKerndatenConnector,
    _parse_notice,
    _parse_source_datetime,
)


MAX_SAMPLE_NOTICES = 8


def test_austria_production_transport_live_smoke():
    now = datetime.now(timezone.utc)
    connector = AustriaKerndatenConnector()
    datasets = connector._discover(type("Cursor", (), {"datasets": {}})())
    cutoff = now - timedelta(days=60)

    evidence = {
        "at": now.isoformat(),
        "dataset_count": len(datasets),
        "kdqs": [],
        "accessible_kdqs": 0,
        "sixty_day_max_selected": 0,
        "sampled_notices": 0,
        "sample_actionable_rows": 0,
        "sample_roots": {},
    }
    sample_budget = MAX_SAMPLE_NOTICES

    for dataset_id, entry in datasets.items():
        for kdq_url in list((entry or {}).get("urls") or []):
            row = {"dataset_id": dataset_id, "kdq_url": kdq_url}
            try:
                items = connector._kdq_items(kdq_url)
                evidence["accessible_kdqs"] += 1
                selected = [
                    item for item in items
                    if (_parse_source_datetime(item.get("lastmod")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
                ]
                row["item_count"] = len(items)
                row["selected_60d"] = len(selected)
                evidence["sixty_day_max_selected"] = max(evidence["sixty_day_max_selected"], len(selected))

                for item in selected[: min(2, sample_budget)]:
                    payload = connector._notice_payload(item["url"])
                    states = _parse_notice(
                        payload,
                        dataset_id=dataset_id,
                        item_id=item["id"],
                        item_lastmod=item["lastmod"],
                        notice_url=item["url"],
                    )
                    evidence["sampled_notices"] += 1
                    evidence["sample_actionable_rows"] += len(states)
                    root = states[0].get("root_family") if states else "non_actionable_or_known_legacy"
                    evidence["sample_roots"][root] = evidence["sample_roots"].get(root, 0) + 1
                    sample_budget -= 1
                    if sample_budget <= 0:
                        break
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
            evidence["kdqs"].append(row)
            if sample_budget <= 0:
                # Continue measuring KDQ indexes but make no more notice requests.
                pass

    assert evidence["accessible_kdqs"] > 0
    assert evidence["sixty_day_max_selected"] <= connector.max_notice_fetches_per_kdq
    assert evidence["sampled_notices"] > 0

    raise AssertionError(
        "AT_KERNDATEN_BOUNDED_PRODUCTION_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000]
    )
