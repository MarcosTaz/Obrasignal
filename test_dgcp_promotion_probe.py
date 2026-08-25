"""TEMPORARY forensic probe; remove after observing live pagination economics."""
from datetime import datetime, timedelta, timezone
import json

import requests

from dominican_republic_dgcp import DGCP_OCDS_RELEASES_URL
from dominican_republic_dgcp_pacc import DGCP_PACC_ACQUISITIONS_URL


def _summary(url, params):
    response = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json", "User-Agent": "ObraSignal temporary promotion probe/1.0"},
        timeout=45,
    )
    response.raise_for_status()
    envelope = response.json()
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    content = payload.get("content") if isinstance(payload, dict) else None
    return {
        "content_len": len(content) if isinstance(content, list) else None,
        "meta": {
            key: envelope.get(key)
            for key in ("page", "limit", "pages", "totalResults")
            if isinstance(envelope, dict) and key in envelope
        },
    }


def test_temporary_dgcp_promotion_metadata_probe():
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    ocds = _summary(
        DGCP_OCDS_RELEASES_URL,
        {
            "page": 1,
            "limit": 1000,
            "start_date": yesterday.isoformat(),
            "end_date": yesterday.isoformat(),
        },
    )
    pacc = _summary(
        DGCP_PACC_ACQUISITIONS_URL,
        {"page": 1, "limit": 1000, "año": today.year},
    )
    raise AssertionError("DGCP_PROMOTION_META=" + json.dumps({"ocds": ocds, "pacc": pacc}, sort_keys=True, default=str))
