"""TEMPORARY last live probe for BZP NoticeUpdateNotice content.

Network-dependent by design. MUST be deleted before merge.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import html
import json
import re

import requests


BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary BZP forensic validator/1.0",
}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(str(data).split())
        if value:
            self.parts.append(value)


def _text(value):
    parser = _TextParser()
    parser.feed(str(value or ""))
    return html.unescape("\n".join(parser.parts))


def _curate(row):
    return {
        key: row.get(key)
        for key in (
            "noticeNumber", "bzpNumber", "publicationDate", "orderObject",
            "orderType", "cpvCode", "submittingOffersDate", "tenderId", "objectId",
        )
    }


def test_poland_bzp_update_html_change_semantics_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")
    end = now.strftime("%Y-%m-%dT23:59:59Z")
    response = session.get(
        BASE,
        params={
            "NoticeType": "NoticeUpdateNotice",
            "PublicationDateFrom": start,
            "PublicationDateTo": end,
            "PageSize": 400,
        },
        timeout=90,
    )
    response.raise_for_status()
    rows = response.json()
    assert isinstance(rows, list) and rows

    matches = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = _text(row.get("htmlBody"))
        lower = text.lower()
        if not any(token in lower for token in (
            "termin składania ofert", "terminu składania ofert", "składania ofert"
        )):
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        relevant = [
            line for line in lines
            if any(token in line.lower() for token in (
                "termin składania", "terminu składania", "składania ofert",
                "zmiana", "przed zmianą", "po zmianie"
            ))
        ][:120]
        dates = sorted(set(re.findall(
            r"(?:\d{4}-\d{2}-\d{2}|\d{2}[.\-/]\d{2}[.\-/]\d{4})(?:\s*(?:r\.)?)?(?:\s+\d{1,2}:\d{2})?",
            text,
        )))[:100]
        matches.append({
            "row": _curate(row),
            "relevant_lines": relevant,
            "date_tokens": dates,
            "html_bytes": len(str(row.get("htmlBody") or "").encode("utf-8")),
        })
        if len(matches) >= 5:
            break

    evidence = {
        "returned": len(rows),
        "matches": matches,
        "match_count_capped": len(matches),
        "all_update_order_types": sorted(set(str(row.get("orderType")) for row in rows if isinstance(row, dict))),
        "all_update_deadlines": sorted(set(str(row.get("submittingOffersDate")) for row in rows if isinstance(row, dict))),
        "cookies": sorted(session.cookies.keys()),
    }
    raise AssertionError(
        "PL_BZP_UPDATE_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000]
    )
