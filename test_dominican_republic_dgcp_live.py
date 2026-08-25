"""Explicit network gate for the Dominican Republic DGCP source.

Normal CI must never depend on this publisher. The dedicated workflow opts in
with ``OBRASIGNAL_LIVE_DGCP=1`` and performs a small bounded discovery+detail
probe. It verifies public machine access and the actual transport contract; it
does not by itself promote the source to production-ready because full
pagination completeness remains a separate runtime gate.
"""
from datetime import datetime, timedelta, timezone
import os

import pytest
import requests

from dominican_republic_dgcp import DGCP_OCDS_RELEASES_URL


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)


def _headers():
    return {
        "Accept": "application/json",
        "User-Agent": "ObraSignal DGCP live contract probe/1.0",
    }


def test_live_dgcp_public_ocds_discovery_and_detail_contract():
    today = datetime.now(timezone.utc).date()
    response = requests.get(
        DGCP_OCDS_RELEASES_URL,
        params={
            "page": 1,
            "limit": 100,
            "start_date": (today - timedelta(days=7)).isoformat(),
            "end_date": today.isoformat(),
        },
        headers=_headers(),
        timeout=45,
    )
    response.raise_for_status()
    envelope = response.json()

    # Live DGCP wraps discovery in its generic API response instead of returning
    # the Swagger OcdsResponse shape directly.
    assert isinstance(envelope, dict)
    assert envelope.get("hasError") is False
    assert envelope.get("code") == 200
    api_payload = envelope.get("payload")
    assert isinstance(api_payload, dict)
    candidates = api_payload.get("content")
    assert isinstance(candidates, list)
    assert candidates, "DGCP returned an unexpected empty seven-day discovery window"

    candidate = next((row for row in candidates if isinstance(row, dict) and row.get("ocid") and row.get("url")), None)
    assert candidate is not None
    assert str(candidate["ocid"]).startswith("ocds-6550wx-")
    assert str(candidate["url"]).startswith("https://datosabiertos.dgcp.gob.do/api-dgcp/v1/ocds/releases")

    detail_response = requests.get(candidate["url"], headers=_headers(), timeout=45)
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert isinstance(detail, dict)

    # Accept either the documented direct OCDS package or the same generic DGCP
    # wrapper used by discovery; the connector normalizer will be pinned to the
    # observed shape after this probe.
    if isinstance(detail.get("payload"), dict):
        detail = detail["payload"]
        if isinstance(detail.get("content"), dict):
            detail = detail["content"]

    releases = detail.get("releases") if isinstance(detail, dict) else None
    assert isinstance(releases, list), f"unexpected DGCP detail keys: {sorted(detail) if isinstance(detail, dict) else type(detail)}"
    assert releases
    sample = next((row for row in releases if isinstance(row, dict)), None)
    assert sample is not None
    assert sample.get("ocid") == candidate["ocid"]
    assert sample.get("date")
    assert isinstance(sample.get("tag"), list)
