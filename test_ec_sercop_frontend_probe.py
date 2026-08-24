"""Temporary forensic probe for official SERCOP monthly OCDS ZIP shape; delete after contract freeze."""
from collections import Counter
from io import BytesIO
import json
import zipfile

import requests

BASE = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA"
URL = f"{BASE}/download?type=json&year=2026&month=8&method=all"
HEADERS = {
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
    "Accept": "application/zip,application/json;q=0.9,*/*;q=0.8",
}


def _brief(value, depth=0):
    if depth >= 3:
        if isinstance(value, (dict, list)):
            return {"type": type(value).__name__, "length": len(value)}
        return str(value)[:240] if value is not None else None
    if isinstance(value, dict):
        return {key: _brief(val, depth + 1) for key, val in list(value.items())[:40]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first": _brief(value[0], depth + 1) if value else None,
        }
    return str(value)[:240] if value is not None else None


def _latest_release(unit):
    if not isinstance(unit, dict):
        return {}
    compiled = unit.get("compiledRelease")
    if isinstance(compiled, dict):
        return compiled
    releases = unit.get("releases")
    if isinstance(releases, list):
        rows = [row for row in releases if isinstance(row, dict)]
        if rows:
            return max(rows, key=lambda row: str(row.get("date") or ""))
    if unit.get("ocid") and (unit.get("tender") or unit.get("tag")):
        return unit
    return {}


def test_current_sercop_month_zip_ocds_shape():
    response = requests.get(URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    assert response.content[:2] == b"PK"

    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 1, names
        raw = archive.read(names[0])
    payload = json.loads(raw)

    if isinstance(payload, list):
        units = [row for row in payload if isinstance(row, dict)]
        root = "list"
        root_keys = []
    elif isinstance(payload, dict):
        root = "dict"
        root_keys = sorted(payload.keys())
        units = []
        for key in ("records", "releases", "packages", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                units = [row for row in value if isinstance(row, dict)]
                break
        if not units and payload:
            units = [payload]
    else:
        raise AssertionError({"payload_type": type(payload).__name__})

    releases = [_latest_release(unit) for unit in units]
    releases = [row for row in releases if row]
    tender_status = Counter()
    main_category = Counter()
    tags = Counter()
    active_future_candidates = []
    for release in releases:
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        tender_status[str(tender.get("status"))] += 1
        main_category[str(tender.get("mainProcurementCategory"))] += 1
        for tag in release.get("tag") or []:
            tags[str(tag)] += 1
        period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
        if str(tender.get("status") or "").lower() == "active" and period.get("endDate"):
            active_future_candidates.append(release)

    first = units[0] if units else {}
    first_release = _latest_release(first)
    diagnostics = {
        "status": response.status_code,
        "zip_bytes": len(response.content),
        "content_type": response.headers.get("content-type"),
        "content_disposition": response.headers.get("content-disposition"),
        "archive_names": names,
        "json_bytes": len(raw),
        "root": root,
        "root_keys": root_keys,
        "unit_count": len(units),
        "first_unit_keys": sorted(first.keys()) if isinstance(first, dict) else [],
        "first_unit": _brief(first),
        "first_release_keys": sorted(first_release.keys()) if isinstance(first_release, dict) else [],
        "first_release": _brief(first_release),
        "tender_status": dict(tender_status),
        "main_category": dict(main_category),
        "tags": dict(tags),
        "active_with_deadline_count": len(active_future_candidates),
        "first_active_with_deadline": _brief(active_future_candidates[0]) if active_future_candidates else None,
    }
    raise AssertionError(diagnostics)
