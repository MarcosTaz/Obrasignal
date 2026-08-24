"""TEMPORARY live forensic probe for Poland BZP pagination/lifecycle semantics.

Network-dependent by design. Delete after evidence is captured; permanent CI
must remain offline/deterministic.
"""
from datetime import datetime, timedelta, timezone
import json
import re

import requests

BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
HEADERS = {"Accept": "application/json", "User-Agent": "ObraSignal temporary BZP forensic validator/1.0"}


def _get(session, params):
    response = session.get(BASE, params=params, timeout=45)
    payload = None
    try:
        payload = response.json()
    except Exception:
        pass
    return response, payload


def _ids(payload):
    if not isinstance(payload, list):
        return []
    return [str(row.get("objectId") or "") for row in payload if isinstance(row, dict)]


def _summary(row):
    if not isinstance(row, dict):
        return row
    keys = (
        "noticeType", "noticeNumber", "bzpNumber", "publicationDate", "orderType",
        "submittingOffersDate", "procedureResult", "tenderId", "objectId", "cpvCode",
        "orderObject",
    )
    return {key: row.get(key) for key in keys if key in row}


def _find_original_contract(session, tender_id, now):
    # Test whether TenderId is an effective server-side filter while finding the
    # original ContractNotice. Broad but bounded window.
    params = {
        "NoticeType": "ContractNotice",
        "TenderId": tender_id,
        "PublicationDateFrom": (now - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z"),
        "PublicationDateTo": now.strftime("%Y-%m-%dT23:59:59Z"),
        "PageSize": 50,
    }
    response, payload = _get(session, params)
    exact = [row for row in (payload or []) if isinstance(row, dict) and row.get("tenderId") == tender_id]
    return response.status_code, len(payload) if isinstance(payload, list) else None, exact


def test_poland_bzp_pagination_and_lifecycle_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)

    # 1) Explicitly test whether PageNumber changes the returned slice.
    base = {
        "NoticeType": "ContractNotice",
        "PublicationDateFrom": start.strftime("%Y-%m-%dT00:00:00Z"),
        "PublicationDateTo": now.strftime("%Y-%m-%dT23:59:59Z"),
        "PageSize": 3,
    }
    page_results = {}
    for page_number in (1, 2, 3):
        response, payload = _get(session, {**base, "PageNumber": page_number})
        page_results[str(page_number)] = {
            "status": response.status_code,
            "ids": _ids(payload),
            "rows": [_summary(row) for row in (payload[:3] if isinstance(payload, list) else [])],
        }

    # 2) Capture real NoticeUpdateNotice examples, prioritising section 8.1
    # (submission deadline) updates and resolving their original Works notice.
    update_params = {
        "NoticeType": "NoticeUpdateNotice",
        "PublicationDateFrom": (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z"),
        "PublicationDateTo": now.strftime("%Y-%m-%dT23:59:59Z"),
        "PageSize": 250,
    }
    update_response, updates = _get(session, update_params)
    update_evidence = []
    works_deadline_update = None
    for row in (updates or []):
        if not isinstance(row, dict):
            continue
        body = str(row.get("htmlBody") or "")
        tender_id = str(row.get("tenderId") or "")
        if not tender_id:
            continue
        interesting = "8.1. Termin składania ofert" in body
        if not interesting and len(update_evidence) >= 4:
            continue
        status, contract_count, contracts = _find_original_contract(session, tender_id, now)
        contract = contracts[0] if contracts else None
        entry = {
            "update": _summary(row),
            "has_8_1": interesting,
            "contract_query_status": status,
            "contract_query_count": contract_count,
            "exact_contract": _summary(contract) if contract else None,
            "update_keys": sorted(row.keys()),
        }
        if interesting:
            text = re.sub(r"<[^>]+>", " | ", body)
            text = re.sub(r"\s+", " ", text)
            pos = text.find("8.1. Termin składania ofert")
            entry["section_8_1_excerpt"] = text[max(0, pos - 100):pos + 500]
        update_evidence.append(entry)
        if interesting and contract and contract.get("orderType") == "Works":
            works_deadline_update = entry
            break
        if len(update_evidence) >= 12:
            break

    # 3) Capture a real TenderResultNotice linked back to a Works contract.
    result_params = {
        "NoticeType": "TenderResultNotice",
        "PublicationDateFrom": (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z"),
        "PublicationDateTo": now.strftime("%Y-%m-%dT23:59:59Z"),
        "PageSize": 250,
    }
    result_response, results = _get(session, result_params)
    works_result = None
    result_samples = []
    for row in (results or []):
        if not isinstance(row, dict):
            continue
        tender_id = str(row.get("tenderId") or "")
        if not tender_id:
            continue
        status, contract_count, contracts = _find_original_contract(session, tender_id, now)
        contract = contracts[0] if contracts else None
        entry = {
            "result": _summary(row),
            "contract_query_status": status,
            "contract_query_count": contract_count,
            "exact_contract": _summary(contract) if contract else None,
            "result_keys": sorted(row.keys()),
        }
        result_samples.append(entry)
        if contract and contract.get("orderType") == "Works":
            works_result = entry
            break
        if len(result_samples) >= 12:
            break

    evidence = {
        "page_number_test": page_results,
        "updates": {
            "status": update_response.status_code,
            "returned": len(updates) if isinstance(updates, list) else None,
            "samples": update_evidence,
            "works_deadline_update": works_deadline_update,
        },
        "results": {
            "status": result_response.status_code,
            "returned": len(results) if isinstance(results, list) else None,
            "samples": result_samples,
            "works_result": works_result,
        },
    }
    raise AssertionError("PL_BZP_TARGET_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000])
