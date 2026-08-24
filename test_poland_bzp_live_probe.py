"""TEMPORARY final live probe for Poland BZP update/deadline semantics.

Network-dependent by design. MUST be deleted before merge.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import html
import json
import re

import requests


BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
STATS = f"{BASE}/stats"
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


def _text_from_html(value):
    parser = _TextParser()
    parser.feed(str(value or ""))
    return html.unescape("\n".join(parser.parts))


def _get_list(session, notice_type, start, end, page_size):
    response = session.get(
        BASE,
        params={
            "NoticeType": notice_type,
            "PublicationDateFrom": start,
            "PublicationDateTo": end,
            "PageSize": page_size,
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, list)
    return [row for row in payload if isinstance(row, dict)]


def _stats(session, start, end):
    response = session.get(
        STATS,
        params={"PublicationDateFrom": start, "PublicationDateTo": end},
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, list)
    return {
        str(row.get("noticeType")): int(row.get("numberOfNotices") or 0)
        for row in payload if isinstance(row, dict) and row.get("noticeType")
    }


def _curate(row):
    return {
        key: row.get(key)
        for key in (
            "noticeType", "noticeNumber", "bzpNumber", "orderType", "tenderType",
            "publicationDate", "orderObject", "cpvCode", "submittingOffersDate",
            "procedureResult", "organizationName", "organizationCity",
            "organizationProvince", "organizationCountry", "tenderId", "objectId",
        )
    }


def test_poland_bzp_update_deadline_and_large_complete_window_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")
    end = now.strftime("%Y-%m-%dT23:59:59Z")

    contracts = _get_list(session, "ContractNotice", start, end, 160)
    updates = _get_list(session, "NoticeUpdateNotice", start, end, 160)
    contract_by_tender = {
        str(row.get("tenderId") or "").strip(): row
        for row in contracts if str(row.get("tenderId") or "").strip()
    }
    linked = None
    for update in updates:
        tender_id = str(update.get("tenderId") or "").strip()
        if tender_id and tender_id in contract_by_tender:
            linked = (contract_by_tender[tender_id], update)
            break
    assert linked is not None, "bounded sample did not contain a ContractNotice/NoticeUpdateNotice link"

    contract, update = linked
    update_text = _text_from_html(update.get("htmlBody"))
    lines = [line.strip() for line in update_text.splitlines() if line.strip()]
    deadline_lines = [
        line for line in lines
        if any(token in line.lower() for token in (
            "termin składania", "składania ofert", "terminu składania", "ofert"
        ))
    ][:80]
    date_tokens = sorted(set(re.findall(
        r"(?:\d{4}-\d{2}-\d{2}|\d{2}[.\-/]\d{2}[.\-/]\d{4})(?:\s*(?:r\.)?)?(?:\s+\d{1,2}:\d{2})?",
        update_text,
    )))[:80]

    # Prove a materially larger pageSize against stats on a complete weekday.
    large_complete = None
    for days_ago in range(1, 15):
        day = (now - timedelta(days=days_ago)).date()
        day_start = f"{day.isoformat()}T00:00:00Z"
        day_end = f"{day.isoformat()}T23:59:59Z"
        counts = _stats(session, day_start, day_end)
        count = counts.get("ContractNotice", 0)
        if 250 < count <= 500:
            rows = _get_list(session, "ContractNotice", day_start, day_end, count)
            large_complete = {
                "start": day_start,
                "stats_count": count,
                "returned_count": len(rows),
                "works_count": sum(1 for row in rows if row.get("orderType") == "Works"),
                "first_id": rows[0].get("objectId") if rows else None,
                "last_id": rows[-1].get("objectId") if rows else None,
            }
            assert len(rows) == count
            break
    assert large_complete is not None, "no recent weekday with 251..500 ContractNotice rows found"

    evidence = {
        "linked": {
            "contract": _curate(contract),
            "update": _curate(update),
            "same_tender_id": contract.get("tenderId") == update.get("tenderId"),
            "update_html_bytes": len(str(update.get("htmlBody") or "").encode("utf-8")),
            "deadline_lines": deadline_lines,
            "date_tokens": date_tokens,
        },
        "large_complete": large_complete,
        "cookies": sorted(session.cookies.keys()),
    }
    raise AssertionError(
        "PL_BZP_FINAL_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000]
    )
