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


def test_tanzania_nest_live_probe():
    package = _json("releases", params=PARAMS)
    releases = package.get("releases") if isinstance(package.get("releases"), list) else []
    ocids = []
    for release in releases:
        if isinstance(release, dict) and release.get("ocid") and release.get("ocid") not in ocids:
            ocids.append(release.get("ocid"))
        if len(ocids) >= 10:
            break

    samples = []
    schemes = {}
    additional_categories = {}
    for ocid in ocids:
        record = _json(f"records/{ocid}")
        compiled = record.get("compiledRelease") if isinstance(record.get("compiledRelease"), dict) else {}
        tender = compiled.get("tender") if isinstance(compiled.get("tender"), dict) else {}
        categories = tender.get("additionalProcurementCategories") if isinstance(tender.get("additionalProcurementCategories"), list) else []
        for category in categories:
            key = str(category)
            additional_categories[key] = additional_categories.get(key, 0) + 1

        classifications = []
        items = tender.get("items") if isinstance(tender.get("items"), list) else []
        for item in items[:5]:
            classification = item.get("classification") if isinstance(item, dict) and isinstance(item.get("classification"), dict) else {}
            if not classification:
                continue
            scheme = str(classification.get("scheme") or "<missing>")
            schemes[scheme] = schemes.get(scheme, 0) + 1
            classifications.append({
                "scheme": classification.get("scheme"),
                "id": classification.get("id"),
                "description": classification.get("description"),
            })
        samples.append({
            "ocid": ocid,
            "status": tender.get("status"),
            "additionalProcurementCategories": categories,
            "classifications": classifications,
            "description": str(tender.get("description") or "")[:200],
        })

    pytest.fail("NEST_TAXONOMY=" + json.dumps({
        "sample_count": len(samples),
        "schemes": schemes,
        "additional_categories": additional_categories,
        "samples": samples,
    }, sort_keys=True, default=str))
