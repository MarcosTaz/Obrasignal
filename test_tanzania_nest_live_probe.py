import json

import requests


def test_tanzania_nest_live_probe():
    url = "https://nest.go.tz/gateway/nest-data-portal-api/api/releases"
    response = requests.get(
        url,
        params={"cursor": "0", "since": "2026-08-01T00:00:00Z"},
        timeout=45,
    )
    print("NEST_PROBE_STATUS", response.status_code)
    print("NEST_PROBE_CONTENT_TYPE", response.headers.get("Content-Type"))
    print("NEST_PROBE_BODY", response.text[:4000])
    response.raise_for_status()
    payload = response.json()
    print("NEST_PROBE_KEYS", sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
    assert isinstance(payload, dict)
