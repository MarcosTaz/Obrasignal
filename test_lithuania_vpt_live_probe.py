"""TEMPORARY Lithuania CVP IS API contract probe.

Delete before merge. The apiKey is the public shared key published verbatim by
Lithuania's Public Procurement Office in its official API instructions.
This probe intentionally fails after bounded evidence is printed.
"""
from datetime import datetime, timezone
import json

import requests

ENDPOINT = "https://viesiejipirkimai.lt/epps-integration/api/cft-details-export"
PUBLIC_API_KEY = "acec29bd-687c-4609-b211-c01b6cf51b55"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "apiKey": PUBLIC_API_KEY,
    "User-Agent": "ObraSignal Lithuania VPT forensic probe/2.0",
}
TARGET_OPEN = 9333230
TARGET_AWARDED = 8009747
MAX_CALLS = 30


def _hint(row):
    if not isinstance(row, dict):
        return None
    keys = (
        "id", "cftCaUniqueId", "caNumber", "datePublished", "status", "activeCycle",
        "procurementType", "cpvCodes", "tenderSubmissionDeadline", "awardDate",
        "contractAwardDate", "contractAwardedInLots", "title",
    )
    return {k: row.get(k) for k in keys if row.get(k) not in (None, "")}


def _parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d-%m-%Y %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def test_lithuania_api_incremental_contract_live():
    session = requests.Session()
    calls = 0
    evidence = {"at": datetime.now(timezone.utc).isoformat(), "page_sizes": {}, "filters": {}, "tail": {}}

    def post(body):
        nonlocal calls
        calls += 1
        assert calls <= MAX_CALLS
        response = session.post(ENDPOINT, headers=HEADERS, json=body, timeout=60)
        try:
            payload = response.json()
        except Exception:
            payload = None
        rows = [r for r in payload if isinstance(r, dict)] if isinstance(payload, list) else []
        return response, rows

    # Determine useful bounded page size. Page 1 is enough to prove server cap.
    for size in (100, 500, 1000, 2000):
        response, rows = post({"pageSize": size, "pageNum": 1})
        evidence["page_sizes"][str(size)] = {
            "status": response.status_code,
            "count": len(rows),
            "first": _hint(rows[0]) if rows else None,
            "last": _hint(rows[-1]) if rows else None,
            "body_prefix": response.text[:500] if response.status_code != 200 else None,
        }

    # Test likely identifier filters individually. Silent ignoring is detected by
    # comparing returned ids with the requested target.
    for key in ("id", "resourceId", "cftCaUniqueId"):
        response, rows = post({"pageSize": 10, "pageNum": 1, key: TARGET_OPEN})
        evidence["filters"][key] = {
            "status": response.status_code,
            "count": len(rows),
            "ids": [r.get("id") for r in rows[:10]],
            "target_returned": any(r.get("id") == TARGET_OPEN for r in rows),
        }

    # Probe recent pages from the previously validated tail. This catches new
    # appends while also measuring cross-page date monotonicity of non-null dates.
    page_bounds = []
    works = []
    first_empty = None
    for page in range(738, 750):
        response, rows = post({"pageSize": 100, "pageNum": page})
        dates = [_parse_date(r.get("datePublished")) for r in rows]
        dates = [d for d in dates if d is not None]
        page_bounds.append({
            "page": page,
            "status": response.status_code,
            "count": len(rows),
            "min": min(dates).isoformat() if dates else None,
            "max": max(dates).isoformat() if dates else None,
            "null_dates": len(rows) - len(dates),
            "first": _hint(rows[0]) if rows else None,
            "last": _hint(rows[-1]) if rows else None,
        })
        works.extend((page, r) for r in rows if str(r.get("procurementType") or "").lower() == "works")
        if not rows and first_empty is None:
            first_empty = page
            break
    evidence["tail"]["bounds"] = page_bounds
    evidence["tail"]["first_empty"] = first_empty
    evidence["tail"]["works"] = [{"page": p, **(_hint(r) or {})} for p, r in works[-20:]]

    # Re-read historical pages containing known open/awarded Works. This proves
    # current lifecycle state is mutable in-place and not discoverable tail-only.
    for name, page, target in (("historic_awarded", 640, TARGET_AWARDED), ("recent_open", 744, TARGET_OPEN)):
        response, rows = post({"pageSize": 100, "pageNum": page})
        hit = next((r for r in rows if r.get("id") == target), None)
        evidence[name] = {"page": page, "status": response.status_code, "hit": _hint(hit)}

    evidence["calls"] = calls
    raise AssertionError("LT_VPT_INCREMENTAL_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:90000])
