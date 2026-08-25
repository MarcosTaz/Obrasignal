"""Explicit live contract probe for Dominican Republic DGCP PACC early signals."""
import os

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)


def test_live_dgcp_pacc_acquisitions_contract():
    response = requests.get(
        f"{DGCP_API_ROOT}/pacc/adquisiciones",
        params={"page": 1, "limit": 10},
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal DGCP PACC live contract probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    envelope = response.json()
    assert isinstance(envelope, dict)
    assert envelope.get("hasError") is False
    assert envelope.get("code") == 200
    payload = envelope.get("payload")
    assert isinstance(payload, dict)
    rows = payload.get("content")
    assert isinstance(rows, list)
    assert rows, "DGCP PACC acquisitions unexpectedly returned no rows"
    sample = next((row for row in rows if isinstance(row, dict)), None)
    assert sample is not None
    # Kept intentionally: field names are contract evidence without logging values.
    print("DGCP_PACC_FIELDS=" + ",".join(sorted(map(str, sample.keys()))))
