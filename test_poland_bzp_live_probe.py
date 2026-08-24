"""TEMPORARY exact-sequence probe for BZP deadline updates.

Network-dependent by design. MUST be deleted before merge.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import html
import json

import requests


BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary BZP forensic validator/1.0",
}


class _PartsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(str(data).split())
        if value:
            self.parts.append(html.unescape(value))


def _parts(value):
    parser = _PartsParser()
    parser.feed(str(value or ""))
    return parser.parts


def test_poland_bzp_exact_deadline_update_sequence_live():
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

    findings = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parts = _parts(row.get("htmlBody"))
        for index, part in enumerate(parts):
            if "8.1. Termin składania ofert" not in part:
                continue
            findings.append({
                "tenderId": row.get("tenderId"),
                "objectId": row.get("objectId"),
                "noticeNumber": row.get("noticeNumber"),
                "publicationDate": row.get("publicationDate"),
                "sequence": parts[index:index + 20],
            })
            break
        if len(findings) >= 5:
            break

    assert findings, "No update containing exact 8.1 deadline section found in bounded sample"
    raise AssertionError(
        "PL_BZP_EXACT_UPDATE_SEQUENCE "
        + json.dumps({"findings": findings}, ensure_ascii=False, sort_keys=True)[:30000]
    )
