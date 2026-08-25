"""TEMPORARY forensic probe; remove after validating /procesos discovery."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json

import requests

from dominican_republic_dgcp import DGCP_API_ROOT


def test_temporary_dgcp_process_discovery_probe():
    day = datetime.now(timezone.utc).date() - timedelta(days=1)
    response = requests.get(
        f"{DGCP_API_ROOT}/procesos",
        params={
            "page": 1,
            "limit": 1000,
            "startdate": day.isoformat(),
            "enddate": day.isoformat(),
        },
        headers={"Accept": "application/json", "User-Agent": "ObraSignal temporary promotion probe/1.0"},
        timeout=45,
    )
    response.raise_for_status()
    envelope = response.json()
    if not isinstance(envelope, dict) or envelope.get("hasError") is not False or envelope.get("code") != 200:
        raise RuntimeError("unexpected DGCP /procesos envelope")
    payload = envelope.get("payload")
    rows = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("DGCP /procesos payload missing content")
    mappings = [row for row in rows if isinstance(row, dict)]
    objects = Counter(str(row.get("objeto_proceso") or "").strip() for row in mappings)
    works = [row for row in mappings if str(row.get("objeto_proceso") or "").strip().lower() == "obras"]
    summary = {
        "day": day.isoformat(),
        "content_len": len(rows),
        "meta": {key: envelope.get(key) for key in ("page", "limit", "pages", "totalResults")},
        "field_keys": sorted(mappings[0]) if mappings else [],
        "object_counts": dict(objects),
        "works_count_in_returned_rows": len(works),
        "works_sample": {
            key: works[0].get(key)
            for key in ("codigo_proceso", "objeto_proceso", "estado_proceso", "fecha_publicacion_proceso")
        } if works else {},
    }
    raise AssertionError("DGCP_PROCESS_DISCOVERY=" + json.dumps(summary, sort_keys=True, default=str))
