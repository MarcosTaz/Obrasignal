"""TEMPORARY live forensic probe for Poland e-Zamowienia BZP WebService.

This test is intentionally network-dependent and MUST be deleted before merge.
It exists only to evidence the official public API contract in GitHub Actions.
"""
from datetime import datetime, timedelta, timezone
import json

import requests


BASE = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary BZP forensic validator/1.0",
}


def _shape(value, depth=0):
    if depth >= 6:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _shape(v, depth + 1) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1)] if value else []
    return type(value).__name__


def _interesting(value, path="", out=None):
    out = [] if out is None else out
    if len(out) >= 180:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _interesting(child, child_path, out)
            if len(out) >= 180:
                break
    elif isinstance(value, list):
        for index, child in enumerate(value[:4]):
            _interesting(child, f"{path}[{index}]", out)
            if len(out) >= 180:
                break
    else:
        leaf = path.rsplit(".", 1)[-1].lower()
        if any(token in leaf for token in (
            "id", "notice", "type", "order", "cpv", "deadline", "date",
            "publication", "submission", "offer", "procedure", "ocid", "page",
            "number", "status", "result", "contract",
        )):
            out.append((path, value))
    return out


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def test_poland_bzp_public_contract_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=14)
    common = {
        "NoticeType": "ContractNotice",
        "PublicationDateFrom": start.strftime("%Y-%m-%dT00:00:00Z"),
        "PublicationDateTo": now.strftime("%Y-%m-%dT23:59:59Z"),
        "PageSize": 10,
    }

    # Probe documentation surfaces without assuming that either is public.
    docs = {}
    for url in (
        "https://ezamowienia.gov.pl/mo-board/swagger/v1/swagger.json",
        "https://ezamowienia.gov.pl/mo-board/swagger/index.html",
        "https://ezamowienia.gov.pl/swagger/v1/swagger.json",
    ):
        response = session.get(url, timeout=30, allow_redirects=True)
        docs[url] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "bytes": len(response.content),
            "final_url": response.url,
        }

    # The official integration page documents the public BZP read service.
    # Start from the smallest likely contract and let the live response decide.
    response = session.get(BASE, params=common, timeout=45)
    payload = _safe_json(response)

    # If pagination is mandatory under another conventional name, record a
    # second bounded attempt. Never keep guessing after these two calls.
    fallback = None
    fallback_payload = None
    if response.status_code >= 400:
        fallback_params = dict(common)
        fallback_params["PageNumber"] = 1
        fallback = session.get(BASE, params=fallback_params, timeout=45)
        fallback_payload = _safe_json(fallback)

    stats_params = {
        "PublicationDateFrom": common["PublicationDateFrom"],
        "PublicationDateTo": common["PublicationDateTo"],
    }
    stats = session.get(f"{BASE}/stats", params=stats_params, timeout=45)
    stats_payload = _safe_json(stats)

    chosen = fallback if fallback is not None and fallback.status_code < 400 else response
    chosen_payload = fallback_payload if chosen is fallback else payload

    human = None
    if chosen.status_code < 400 and chosen_payload is not None:
        candidates = chosen_payload if isinstance(chosen_payload, list) else []
        if isinstance(chosen_payload, dict):
            for key in ("items", "notices", "data", "results", "content"):
                if isinstance(chosen_payload.get(key), list):
                    candidates = chosen_payload[key]
                    break
        first = candidates[0] if candidates and isinstance(candidates[0], dict) else None
        if first:
            notice_id = str(
                first.get("objectId") or first.get("noticeId") or first.get("id") or ""
            ).strip()
            if notice_id:
                url = f"https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{notice_id}"
                page = session.get(url, timeout=45, allow_redirects=True)
                human = {
                    "requested": url,
                    "status": page.status_code,
                    "final_url": page.url,
                    "content_type": page.headers.get("content-type"),
                    "bytes": len(page.content),
                }

    evidence = {
        "query": common,
        "primary": {
            "status": response.status_code,
            "url": response.url,
            "content_type": response.headers.get("content-type"),
            "body_prefix": response.text[:3000],
            "shape": _shape(payload),
            "interesting": _interesting(payload) if payload is not None else [],
        },
        "fallback": None if fallback is None else {
            "status": fallback.status_code,
            "url": fallback.url,
            "content_type": fallback.headers.get("content-type"),
            "body_prefix": fallback.text[:3000],
            "shape": _shape(fallback_payload),
            "interesting": _interesting(fallback_payload) if fallback_payload is not None else [],
        },
        "stats": {
            "status": stats.status_code,
            "url": stats.url,
            "content_type": stats.headers.get("content-type"),
            "body_prefix": stats.text[:3000],
            "shape": _shape(stats_payload),
            "interesting": _interesting(stats_payload) if stats_payload is not None else [],
        },
        "docs": docs,
        "human": human,
        "cookies": sorted(session.cookies.keys()),
    }

    # One-run forensic stop so CI preserves the real upstream shape. This file
    # is temporary and will be replaced by deterministic offline tests.
    raise AssertionError(
        "PL_BZP_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:45000]
    )
