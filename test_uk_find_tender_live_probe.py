"""Temporary forensic probe for Find a Tender public OCDS output; delete after contract freeze."""
from datetime import datetime, timezone

import requests

URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement connector research/0.1 (+official open-data validation)",
}


def _summary(value, depth=0):
    if depth >= 3:
        if isinstance(value, (dict, list)):
            return {"type": type(value).__name__, "length": len(value)}
        return value
    if isinstance(value, dict):
        return {k: _summary(v, depth + 1) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "first": _summary(value[0], depth + 1) if value else None}
    return value


def test_find_tender_public_ocds_cursor_shape_live():
    params = {
        "updatedFrom": "2026-08-23T00:00:00",
        "updatedTo": "2026-08-24T23:59:59",
        "stages": "tender",
        "limit": "2",
    }
    response = requests.get(URL, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    releases = payload.get("releases") if isinstance(payload, dict) else None
    first = releases[0] if isinstance(releases, list) and releases else {}
    diagnostics = {
        "status": response.status_code,
        "url": response.url,
        "root_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "release_count": len(releases) if isinstance(releases, list) else None,
        "publishedDate": payload.get("publishedDate") if isinstance(payload, dict) else None,
        "license": payload.get("license") if isinstance(payload, dict) else None,
        "links": payload.get("links") if isinstance(payload, dict) else None,
        "first_summary": _summary(first),
    }
    raise AssertionError(diagnostics)
