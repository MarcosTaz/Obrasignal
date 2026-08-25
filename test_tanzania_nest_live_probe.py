import json

import pytest
import requests


BASE = "https://nest.go.tz/gateway/nest-data-portal-api/api"
PARAMS = {"cursor": "0", "since": "2026-08-01T00:00:00Z"}


def _json(path):
    response = requests.get(f"{BASE}/{path}", params=PARAMS, timeout=45)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def _safe_links(value):
    if isinstance(value, dict):
        return {str(k): str(v)[:1000] for k, v in value.items()}
    if isinstance(value, list):
        return [str(v)[:1000] for v in value]
    return value


def test_tanzania_nest_live_probe():
    releases_package = _json("releases")
    records_package = _json("records")

    records = records_package.get("records") if isinstance(records_package.get("records"), list) else []
    first = records[0] if records and isinstance(records[0], dict) else {}
    compiled = first.get("compiledRelease") if isinstance(first.get("compiledRelease"), dict) else {}
    tender = compiled.get("tender") if isinstance(compiled.get("tender"), dict) else {}

    categories = {}
    statuses = {}
    works_examples = []
    records_with_tender = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        current = record.get("compiledRelease") if isinstance(record.get("compiledRelease"), dict) else {}
        current_tender = current.get("tender") if isinstance(current.get("tender"), dict) else {}
        if not current_tender:
            continue
        records_with_tender += 1
        category = str(current_tender.get("mainProcurementCategory") or "<missing>")
        status = str(current_tender.get("status") or "<missing>")
        categories[category] = categories.get(category, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1
        if category.lower() == "works" and len(works_examples) < 3:
            works_examples.append({
                "ocid": record.get("ocid") or current.get("ocid"),
                "status": current_tender.get("status"),
                "endDate": (current_tender.get("tenderPeriod") or {}).get("endDate") if isinstance(current_tender.get("tenderPeriod"), dict) else None,
            })

    metadata = {
        "release_links": _safe_links(releases_package.get("links")),
        "record_top_keys": sorted(records_package.keys()),
        "record_count": len(records),
        "record_links": _safe_links(records_package.get("links")),
        "first_record_keys": sorted(first.keys()),
        "first_compiled_keys": sorted(compiled.keys()),
        "first_tender_keys": sorted(tender.keys()),
        "records_with_tender": records_with_tender,
        "categories": categories,
        "statuses": statuses,
        "works_examples": works_examples,
        "publishedDate": records_package.get("publishedDate"),
        "license": records_package.get("license"),
        "publicationPolicy": records_package.get("publicationPolicy"),
    }
    pytest.fail("NEST_RECORD_SHAPE=" + json.dumps(metadata, sort_keys=True, default=str))
