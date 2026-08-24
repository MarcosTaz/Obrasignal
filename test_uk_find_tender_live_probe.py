"""Temporary forensic probe for Find a Tender public OCDS output; delete after contract freeze."""

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
        return {k: _summary(v, depth + 1) for k, v in list(value.items())[:60]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "first": _summary(value[0], depth + 1) if value else None}
    text = str(value) if value is not None else None
    return text[:500] if isinstance(text, str) else text


def _probe(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    releases = payload.get("releases") if isinstance(payload, dict) else None
    interesting_headers = {
        key: value for key, value in response.headers.items()
        if key.lower() in {"link", "retry-after", "x-next-cursor", "x-cursor", "content-type"}
        or "cursor" in key.lower()
    }
    return {
        "status": response.status_code,
        "url": response.url,
        "root_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "uri": payload.get("uri") if isinstance(payload, dict) else None,
        "publishedDate": payload.get("publishedDate") if isinstance(payload, dict) else None,
        "license": payload.get("license") if isinstance(payload, dict) else None,
        "links": payload.get("links") if isinstance(payload, dict) else None,
        "release_count": len(releases) if isinstance(releases, list) else None,
        "release_ids": [row.get("id") for row in releases[:5] if isinstance(row, dict)] if isinstance(releases, list) else [],
        "release_dates": [row.get("date") for row in releases[:5] if isinstance(row, dict)] if isinstance(releases, list) else [],
        "first_summary": _summary(releases[0]) if isinstance(releases, list) and releases else None,
        "headers": interesting_headers,
    }


def test_find_tender_public_ocds_cursor_shape_live():
    diagnostics = {
        "known_2026_ocid": _probe(f"{URL}/ocds-h6vhtk-0503cc"),
        "known_2026_notice": _probe(f"{URL}/065280-2026"),
        "wide_window_limit_2": _probe(
            URL,
            {
                "updatedFrom": "2026-07-01T00:00:00",
                "updatedTo": "2026-08-24T23:59:59",
                "limit": "2",
            },
        ),
    }
    raise AssertionError(diagnostics)
