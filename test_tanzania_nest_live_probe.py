import json

import pytest
import requests


def test_tanzania_nest_live_probe():
    url = "https://nest.go.tz/gateway/nest-data-portal-api/api/releases"
    response = requests.get(
        url,
        params={"cursor": "0", "since": "2026-08-01T00:00:00Z"},
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict)

    releases = payload.get("releases") if isinstance(payload.get("releases"), list) else []
    first = releases[0] if releases and isinstance(releases[0], dict) else {}
    tender = first.get("tender") if isinstance(first.get("tender"), dict) else {}
    metadata = {
        "top_keys": sorted(payload.keys()),
        "release_count": len(releases),
        "payload_scalar_metadata": {
            key: value
            for key, value in payload.items()
            if key != "releases" and isinstance(value, (str, int, float, bool, type(None)))
        },
        "first_release_keys": sorted(first.keys()),
        "first_ocid": first.get("ocid"),
        "first_tag": first.get("tag"),
        "first_tender_keys": sorted(tender.keys()),
        "first_tender_status": tender.get("status"),
        "first_main_category": tender.get("mainProcurementCategory"),
    }
    pytest.fail("NEST_LIVE_SHAPE=" + json.dumps(metadata, sort_keys=True, default=str))
