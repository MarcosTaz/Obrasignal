"""TEMPORARY forensic probe; remove after validating /procesos discovery shape."""
from datetime import datetime, timedelta, timezone
import json

import requests

from dominican_republic_dgcp import DGCP_API_ROOT


def test_temporary_dgcp_process_shape_probe():
    day = datetime.now(timezone.utc).date() - timedelta(days=1)
    response = requests.get(
        f"{DGCP_API_ROOT}/procesos",
        params={"page": 1, "limit": 1000, "startdate": day.isoformat(), "enddate": day.isoformat()},
        headers={"Accept": "application/json", "User-Agent": "ObraSignal temporary promotion probe/1.0"},
        timeout=45,
    )
    response.raise_for_status()
    envelope = response.json()
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    if isinstance(payload, list):
        first = payload[0] if payload and isinstance(payload[0], dict) else None
        payload_summary = {"type": "list", "len": len(payload), "first_keys": sorted(first) if first else []}
    elif isinstance(payload, dict):
        first_list = next((value for value in payload.values() if isinstance(value, list)), None)
        first = first_list[0] if first_list and isinstance(first_list[0], dict) else None
        payload_summary = {
            "type": "dict",
            "keys": sorted(payload),
            "first_list_len": len(first_list) if isinstance(first_list, list) else None,
            "first_keys": sorted(first) if first else [],
        }
    else:
        payload_summary = {"type": type(payload).__name__}
    summary = {
        "day": day.isoformat(),
        "envelope_keys": sorted(envelope) if isinstance(envelope, dict) else [],
        "meta": {key: envelope.get(key) for key in ("page", "limit", "pages", "totalResults") if isinstance(envelope, dict)},
        "payload": payload_summary,
    }
    raise AssertionError("DGCP_PROCESS_SHAPE=" + json.dumps(summary, sort_keys=True, default=str))
