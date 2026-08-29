"""Explicit network contract probe for Peru OECE open-contracting data.

The source is public. This test verifies the current official file-index contract
without downloading the potentially large OCDS ZIP payload itself.
"""
import os

import pytest
import requests


OECE_FILES_URL = "https://contratacionesabiertas.oece.gob.pe/api/v1/files"

pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_OECE") != "1",
    reason="live OECE probe is explicit opt-in only",
)


def test_live_oece_bulk_index_contract():
    response = requests.get(
        OECE_FILES_URL,
        params={"page": 1, "paginateBy": 10, "format": "json"},
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal OECE live contract probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()

    assert isinstance(payload, dict)
    results = payload.get("results")
    pagination = payload.get("pagination")
    assert isinstance(results, list)
    assert results, "OECE returned an unexpected empty files index"
    assert isinstance(pagination, dict)
    assert int(pagination.get("num_pages") or 0) >= 1

    item = next((value for value in results if isinstance(value, dict) and isinstance(value.get("files"), dict)), None)
    assert item is not None
    json_url = str(item["files"].get("json") or "").replace(".osce.", ".oece.")
    assert json_url.startswith("https://contratacionesabiertas.oece.gob.pe/")
    assert json_url.lower().endswith(".zip")
