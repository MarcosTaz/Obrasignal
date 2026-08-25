"""Explicit network gate for the Dominican Republic DGCP source.

Normal CI must never depend on this publisher. The dedicated workflow opts in
with ``OBRASIGNAL_LIVE_DGCP=1`` and performs a small, bounded first-page probe.
It proves public machine access and the documented OCDS package shape; it does
not by itself promote the source to production-ready because full pagination
completeness remains a separate runtime gate.
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


def test_live_dgcp_public_ocds_release_contract():
    today = datetime.now(timezone.utc).date()
    response = requests.get(
        DGCP_OCDS_RELEASES_URL,
        params={
            "page": 1,
            "limit": 100,
            "start_date": (today - timedelta(days=7)).isoformat(),
            "end_date": today.isoformat(),
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal DGCP live contract probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()

    assert isinstance(payload, dict)
    assert str(payload.get("version") or "").startswith("1.")
    releases = payload.get("releases")
    assert isinstance(releases, list)
    assert releases, "DGCP returned an unexpected empty seven-day OCDS window"

    sample = next((row for row in releases if isinstance(row, dict)), None)
    assert sample is not None
    assert str(sample.get("ocid") or "").startswith("ocds-6550wx-")
    assert sample.get("date")
    assert isinstance(sample.get("tag"), list)
