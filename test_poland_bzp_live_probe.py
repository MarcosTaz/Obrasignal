"""TEMPORARY low-load live probe for Poland BZP lifecycle semantics.

Network-dependent by design. Delete after evidence is captured; permanent CI
must remain offline/deterministic. PageNumber non-pagination was already proved
in run #729, so this probe only closes update/result notice semantics.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import html
import json

import requests

BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
STATS = f"{BASE}/stats"
HEADERS = {"Accept": "application/json", "User-Agent": "ObraSignal temporary BZP forensic validator/1.0"}


class Parts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(str(data).split())
        if value:
            self.parts.append(html.unescape(value))


def _parts(body):
    parser = Parts()
    parser.feed(str(body or ""))
    return parser.parts


def _json(session, url, params):
    response = session.get(url, params=params, timeout=45)
    payload = None
    try:
        payload = response.json()
    except Exception:
        pass
    return response, payload


def _summary(row):
    if not isinstance(row, dict):
        return row
    keys = (
        "noticeType", "noticeNumber", "bzpNumber", "publicationDate", "orderType",
        "submittingOffersDate", "procedureResult", "tenderId", "objectId", "cpvCode",
        "orderObject",
    )
    return {key: row.get(key) for key in keys if key in row}


def _day_bounds(day):
    return (
        day.strftime("%Y-%m-%dT00:00:00Z"),
        day.strftime("%Y-%m-%dT23:59:59.999999Z"),
    )


def _day_counts(session, day):
    start, end = _day_bounds(day)
    response, payload = _json(session, STATS, {"PublicationDateFrom": start, "PublicationDateTo": end})
    counts = {}
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                try:
                    counts[str(row.get("noticeType") or "")] = int(row.get("numberOfNotices") or 0)
                except (TypeError, ValueError):
                    pass
    return response.status_code, counts


def _fetch_day(session, day, notice_type, count):
    start, end = _day_bounds(day)
    response, payload = _json(session, BASE, {
        "NoticeType": notice_type,
        "PublicationDateFrom": start,
        "PublicationDateTo": end,
        "PageSize": max(1, min(int(count or 1), 250)),
    })
    return response, payload


def test_poland_bzp_lifecycle_templates_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    today = datetime.now(timezone.utc).date()

    day_stats = []
    deadline_update = None
    update_samples = []
    result_samples = []

    # Bounded daily slices prevent the broad 30-day requests/back-lookups that
    # caused upstream 503s in the previous exploratory probe.
    for offset in range(0, 14):
        day = today - timedelta(days=offset)
        status, counts = _day_counts(session, day)
        day_stats.append({"day": day.isoformat(), "status": status, "counts": counts})
        if status != 200:
            continue

        update_count = counts.get("NoticeUpdateNotice", 0)
        if deadline_update is None and 0 < update_count <= 250:
            response, rows = _fetch_day(session, day, "NoticeUpdateNotice", update_count)
            if response.status_code == 200 and isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if len(update_samples) < 3:
                        update_samples.append({"row": _summary(row), "keys": sorted(row.keys())})
                    parts = _parts(row.get("htmlBody"))
                    positions = [i for i, value in enumerate(parts) if "8.1. Termin składania ofert" in value]
                    if positions:
                        index = positions[0]
                        deadline_update = {
                            "row": _summary(row),
                            "keys": sorted(row.keys()),
                            "parts_around_8_1": parts[index:index + 8],
                        }
                        break

        result_count = counts.get("TenderResultNotice", 0)
        if not result_samples and 0 < result_count <= 250:
            response, rows = _fetch_day(session, day, "TenderResultNotice", result_count)
            if response.status_code == 200 and isinstance(rows, list):
                for row in rows[:5]:
                    if isinstance(row, dict):
                        result_samples.append({"row": _summary(row), "keys": sorted(row.keys())})

        if deadline_update is not None and result_samples:
            break

    evidence = {
        "day_stats": day_stats,
        "deadline_update": deadline_update,
        "update_samples": update_samples,
        "result_samples": result_samples,
    }
    raise AssertionError("PL_BZP_LIFECYCLE_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000])
