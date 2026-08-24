"""Temporary live probe: SERCOP modern record endpoint shape.

Delete after the production parser is validated against current official output.
"""
import requests

RECORD_URL = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/record"
OCID = "ocds-5wno2w-LICO-PM-2026-00007-116388"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement connector research/0.1 (+official open-data validation)",
}


def _release_state(release):
    tender = release.get("tender") if isinstance(release, dict) and isinstance(release.get("tender"), dict) else {}
    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    return {
        "id": release.get("id") if isinstance(release, dict) else None,
        "ocid": release.get("ocid") if isinstance(release, dict) else None,
        "date": release.get("date") if isinstance(release, dict) else None,
        "tag": release.get("tag") if isinstance(release, dict) else None,
        "release_keys": sorted(release.keys()) if isinstance(release, dict) else None,
        "tender_keys": sorted(tender.keys()),
        "status": tender.get("status"),
        "category": tender.get("mainProcurementCategory"),
        "deadline": period.get("endDate"),
        "title": tender.get("title"),
    }


def test_sercop_modern_record_shape_live():
    response = requests.get(RECORD_URL, params={"ocid": OCID}, headers=HEADERS, timeout=45)
    response.raise_for_status()
    payload = response.json()
    diagnostics = {
        "status": response.status_code,
        "root_type": type(payload).__name__,
        "root_keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
        "license": payload.get("license") if isinstance(payload, dict) else None,
        "version": payload.get("version") if isinstance(payload, dict) else None,
        "publishedDate": payload.get("publishedDate") if isinstance(payload, dict) else None,
    }

    releases = []
    shape = None
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        shape = "record_package"
        records = [row for row in payload["records"] if isinstance(row, dict)]
        diagnostics["record_count"] = len(records)
        target = next((row for row in records if row.get("ocid") == OCID), records[0] if len(records) == 1 else None)
        if target:
            diagnostics["record_keys"] = sorted(target.keys())
            releases = [row for row in (target.get("releases") or []) if isinstance(row, dict)]
            compiled = target.get("compiledRelease")
            diagnostics["compiled_release"] = _release_state(compiled) if isinstance(compiled, dict) else None
    elif isinstance(payload, dict) and isinstance(payload.get("releases"), list):
        shape = "release_package"
        releases = [row for row in payload["releases"] if isinstance(row, dict)]
    diagnostics["shape"] = shape
    diagnostics["release_count"] = len(releases)
    diagnostics["release_states"] = [_release_state(row) for row in releases[-10:]]
    raise AssertionError(diagnostics)
