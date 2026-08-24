"""TEMPORARY ANAC OCDS bulk-path probe. Delete before merge.

The path shape is taken from ANAC's published OCDS bulk resources. This probe
checks whether the same official month-partitioned route is live for 2026.
It intentionally fails after printing bounded evidence.
"""
from __future__ import annotations

import json

import requests

BASE = "https://dati.anticorruzione.it/opendata/download/dataset/ocds/filesystem/bulk"
UA = "ObraSignal ANAC OCDS forensic probe/1.0"
TARGETS = ((2025, 12), (2026, 1), (2026, 7), (2026, 8))


def _probe(session, year, month):
    url = f"{BASE}/{year}/{month:02d}.json"
    response = session.get(
        url,
        headers={"Accept": "application/json,*/*", "User-Agent": UA, "Range": "bytes=0-262143"},
        timeout=60,
        stream=True,
        allow_redirects=True,
    )
    data = b""
    try:
        if response.status_code in (200, 206):
            for chunk in response.iter_content(65536):
                data += chunk
                if len(data) >= 262144:
                    break
    finally:
        response.close()
    text = data[:262144].decode("utf-8", errors="replace")
    return {
        "url": url,
        "status": response.status_code,
        "final_url": response.url,
        "content_type": response.headers.get("content-type"),
        "content_length": response.headers.get("content-length"),
        "content_range": response.headers.get("content-range"),
        "sample_bytes": len(data),
        "prefix": text[:5000],
        "ocds_markers": {
            "releases": '"releases"' in text,
            "ocid": '"ocid"' in text,
            "tender": '"tender"' in text,
            "date": '"date"' in text,
        },
    }


def test_anac_ocds_monthly_bulk_routes_live():
    session = requests.Session()
    evidence = {f"{y}-{m:02d}": _probe(session, y, m) for y, m in TARGETS}
    raise AssertionError("ANAC_OCDS_BULK_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000])
