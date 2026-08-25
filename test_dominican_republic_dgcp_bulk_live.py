"""Bounded live transport probe for DGCP bulk process/contract exports.

Full historical process XLSX was experimentally observed to exceed 64 MiB on
2026-08-25. Production must therefore not blindly download the full-history file.
The publisher UI advertises year/semester partitions, but those links are not a
stable documented API contract, so partition discovery is intentionally excluded
from permanent CI.
"""
import os

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)


def _probe_transport(path):
    with requests.get(
        f"{DGCP_API_ROOT}{path}",
        headers={
            "Accept": "*/*",
            "User-Agent": "ObraSignal DGCP bulk live contract probe/1.0",
        },
        timeout=45,
        stream=True,
    ) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        disposition = response.headers.get("Content-Disposition", "")
        first = next(response.iter_content(chunk_size=4096), b"")
        assert first.startswith(b"PK"), f"DGCP bulk endpoint {path} is not XLSX/ZIP"
        assert "spreadsheetml" in content_type.lower() or ".xlsx" in disposition.lower()
        return content_type, disposition


def test_live_dgcp_bulk_transports():
    process_type, process_disposition = _probe_transport("/tablas/procesos")
    contract_type, contract_disposition = _probe_transport("/tablas/contratos")
    assert process_type or process_disposition
    assert contract_type or contract_disposition
