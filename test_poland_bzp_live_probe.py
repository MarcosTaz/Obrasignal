"""TEMPORARY live forensic probe for Poland e-Zamowienia BZP WebService.

This test is intentionally network-dependent and MUST be deleted before merge.
It exists only to evidence completeness/lifecycle semantics of the official API.
"""
from datetime import datetime, timedelta, timezone
import json

import requests


BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
STATS = f"{BASE}/stats"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary BZP forensic validator/1.0",
}


def _get_list(session, *, notice_type, start, end, page_size, extras=None):
    params = {
        "NoticeType": notice_type,
        "PublicationDateFrom": start,
        "PublicationDateTo": end,
        "PageSize": page_size,
    }
    params.update(extras or {})
    response = session.get(BASE, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, list)
    assert all(isinstance(row, dict) for row in payload)
    return response, payload


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
    if not isinstance(row, dict):
        return None
    return {
        key: row.get(key)
        for key in (
            "noticeType", "noticeNumber", "bzpNumber", "orderType", "tenderType",
            "publicationDate", "orderObject", "cpvCode", "submittingOffersDate",
            "procedureResult", "organizationName", "organizationCity",
            "organizationProvince", "organizationCountry", "tenderId", "objectId",
            "contractors",
        )
    }


def _works(rows):
    return [row for row in rows if str(row.get("orderType") or "").strip() == "Works"]


def test_poland_bzp_paging_completeness_and_lifecycle_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=14)
    start = start_dt.strftime("%Y-%m-%dT00:00:00Z")
    end = now.strftime("%Y-%m-%dT23:59:59Z")

    stats = _stats(session, start, end)
    assert stats.get("ContractNotice", 0) > 100
    assert stats.get("NoticeUpdateNotice", 0) > 0
    assert stats.get("TenderResultNotice", 0) > 0

    # Determine whether the conventional PageNumber query has any semantics.
    _, base3 = _get_list(
        session, notice_type="ContractNotice", start=start, end=end, page_size=3
    )
    _, page1 = _get_list(
        session, notice_type="ContractNotice", start=start, end=end, page_size=3,
        extras={"PageNumber": 1},
    )
    _, page2 = _get_list(
        session, notice_type="ContractNotice", start=start, end=end, page_size=3,
        extras={"PageNumber": 2},
    )
    ids = lambda rows: [str(row.get("objectId") or "") for row in rows]
    paging = {
        "default": ids(base3),
        "page1": ids(page1),
        "page2": ids(page2),
    }

    # pageSize itself is effective and deterministic for the same time window.
    _, twelve = _get_list(
        session, notice_type="ContractNotice", start=start, end=end, page_size=12
    )
    assert len(base3) == 3
    assert len(twelve) == 12
    assert ids(twelve)[:3] == ids(base3)

    # Capture bounded samples of publisher-native lifecycle notice types.
    samples = {}
    full_by_type = {}
    for notice_type in ("ContractNotice", "NoticeUpdateNotice", "TenderResultNotice", "ContractPerformingNotice"):
        _, rows = _get_list(
            session, notice_type=notice_type, start=start, end=end, page_size=80
        )
        full_by_type[notice_type] = rows
        works = _works(rows)
        samples[notice_type] = {
            "count_returned": len(rows),
            "works_count": len(works),
            "first": _curate(rows[0]) if rows else None,
            "first_works": _curate(works[0]) if works else None,
        }

    assert samples["ContractNotice"]["works_count"] > 0
    assert samples["NoticeUpdateNotice"]["works_count"] > 0
    assert samples["TenderResultNotice"]["works_count"] > 0

    # Look for actual same-procedure linkage across notice types. This is only
    # evidentiary: absence in the bounded sample is reported, not fabricated.
    tender_sets = {
        notice_type: {
            str(row.get("tenderId") or "").strip()
            for row in rows if str(row.get("tenderId") or "").strip()
        }
        for notice_type, rows in full_by_type.items()
    }
    overlaps = {}
    contract_ids = tender_sets["ContractNotice"]
    for notice_type in ("NoticeUpdateNotice", "TenderResultNotice", "ContractPerformingNotice"):
        common = sorted(contract_ids & tender_sets[notice_type])
        overlaps[notice_type] = common[:10]

    linked = {}
    for notice_type, common in overlaps.items():
        if not common:
            linked[notice_type] = None
            continue
        tender_id = common[0]
        linked[notice_type] = {
            "tenderId": tender_id,
            "contract": _curate(next(row for row in full_by_type["ContractNotice"] if row.get("tenderId") == tender_id)),
            "related": _curate(next(row for row in full_by_type[notice_type] if row.get("tenderId") == tender_id)),
        }

    # Probe one smaller day window against stats to establish the completeness
    # primitive: if stats count <= requested pageSize, list length must equal it.
    complete_window = None
    for days_ago in range(1, 15):
        day = (now - timedelta(days=days_ago)).date()
        day_start = f"{day.isoformat()}T00:00:00Z"
        day_end = f"{day.isoformat()}T23:59:59Z"
        day_stats = _stats(session, day_start, day_end)
        count = day_stats.get("ContractNotice", 0)
        if 0 < count <= 200:
            _, rows = _get_list(
                session, notice_type="ContractNotice", start=day_start, end=day_end,
                page_size=count,
            )
            complete_window = {
                "start": day_start,
                "end": day_end,
                "stats_count": count,
                "returned_count": len(rows),
                "first_id": str(rows[0].get("objectId") or "") if rows else None,
                "last_id": str(rows[-1].get("objectId") or "") if rows else None,
            }
            assert len(rows) == count
            break

    assert complete_window is not None

    evidence = {
        "window": {"from": start, "to": end},
        "stats": {key: stats.get(key) for key in (
            "ContractNotice", "NoticeUpdateNotice", "TenderResultNotice",
            "ContractPerformingNotice", "SmallContractNotice",
        )},
        "paging": paging,
        "page_number_changes_results": (
            paging["default"] != paging["page1"] or paging["default"] != paging["page2"]
        ),
        "page_size": {"size3": len(base3), "size12": len(twelve)},
        "samples": samples,
        "tender_id_overlaps": overlaps,
        "linked_examples": linked,
        "complete_window": complete_window,
        "cookies": sorted(session.cookies.keys()),
    }

    # One-run forensic stop. The probe will be deleted after inspection and
    # replaced with deterministic offline tests.
    raise AssertionError(
        "PL_BZP_TARGET_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000]
    )
