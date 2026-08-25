import json

import pytest
import requests


BASE = "https://nest.go.tz/gateway/nest-data-portal-api/api"
PARAMS = {"cursor": "0", "since": "2026-08-01T00:00:00Z"}


def _json(path, *, params=None):
    response = requests.get(f"{BASE}/{path}", params=params, timeout=45)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def _safe_links(value):
    if isinstance(value, dict):
        return {str(k): str(v)[:1000] for k, v in value.items()}
    return value


def test_tanzania_nest_live_probe():
    package = _json("releases", params=PARAMS)
    releases = package.get("releases") if isinstance(package.get("releases"), list) else []

    release_categories = {}
    release_statuses = {}
    releases_with_tender = 0
    works_release_examples = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        if not tender:
            continue
        releases_with_tender += 1
        category = str(tender.get("mainProcurementCategory") or "<missing>")
        status = str(tender.get("status") or "<missing>")
        release_categories[category] = release_categories.get(category, 0) + 1
        release_statuses[status] = release_statuses.get(status, 0) + 1
        if category.lower() == "works" and len(works_release_examples) < 3:
            works_release_examples.append({
                "ocid": release.get("ocid"),
                "status": tender.get("status"),
                "endDate": (tender.get("tenderPeriod") or {}).get("endDate") if isinstance(tender.get("tenderPeriod"), dict) else None,
            })

    first_release = next((row for row in releases if isinstance(row, dict) and row.get("ocid")), {})
    first_ocid = first_release.get("ocid")
    hydrated = _json(f"records/{first_ocid}") if first_ocid else {}
    record_rows = hydrated.get("records") if isinstance(hydrated.get("records"), list) else []
    if record_rows:
        record = record_rows[0] if isinstance(record_rows[0], dict) else {}
    elif hydrated.get("ocid"):
        record = hydrated
    else:
        record = {}
    compiled = record.get("compiledRelease") if isinstance(record.get("compiledRelease"), dict) else {}
    tender = compiled.get("tender") if isinstance(compiled.get("tender"), dict) else {}

    metadata = {
        "release_count": len(releases),
        "release_links": _safe_links(package.get("links")),
        "releases_with_tender": releases_with_tender,
        "release_categories": release_categories,
        "release_statuses": release_statuses,
        "works_release_examples": works_release_examples,
        "hydrated_top_keys": sorted(hydrated.keys()),
        "hydrated_record_count": len(record_rows),
        "hydrated_record_keys": sorted(record.keys()),
        "hydrated_compiled_keys": sorted(compiled.keys()),
        "hydrated_tender_keys": sorted(tender.keys()),
        "hydrated_tender_status": tender.get("status"),
        "hydrated_main_category": tender.get("mainProcurementCategory"),
        "hydrated_ocid": record.get("ocid") or compiled.get("ocid"),
        "publishedDate": package.get("publishedDate"),
    }
    pytest.fail("NEST_HYDRATION_SHAPE=" + json.dumps(metadata, sort_keys=True, default=str))
