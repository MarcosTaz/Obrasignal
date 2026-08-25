"""TEMPORARY forensic probe; remove after validating /procesos content shape."""
from datetime import datetime, timedelta, timezone
import json

import requests

from dominican_republic_dgcp import DGCP_API_ROOT


def test_temporary_dgcp_process_content_probe():
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
    content = payload.get("content") if isinstance(payload, dict) else None
    if isinstance(content, dict):
        nested_list = next((value for value in content.values() if isinstance(value, list)), None)
        first = nested_list[0] if nested_list and isinstance(nested_list[0], dict) else None
        content_summary = {
            "type": "dict",
            "keys": sorted(content),
            "nested_list_len": len(nested_list) if isinstance(nested_list, list) else None,
            "first_keys": sorted(first) if first else [],
        }
    elif isinstance(content, list):
        first = content[0] if content and isinstance(content[0], dict) else None
        content_summary = {"type": "list", "len": len(content), "first_keys": sorted(first) if first else []}
    else:
        content_summary = {"type": type(content).__name__, "preview": str(content)[:200]}
    summary = {
        "day": day.isoformat(),
        "envelope_keys": sorted(envelope) if isinstance(envelope, dict) else [],
        "meta": {key: envelope.get(key) for key in ("page", "limit", "pages", "totalResults") if isinstance(envelope, dict)},
        "content": content_summary,
    }
    raise AssertionError("DGCP_PROCESS_CONTENT=" + json.dumps(summary, sort_keys=True, default=str))
