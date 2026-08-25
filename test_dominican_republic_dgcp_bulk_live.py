"""Bounded live probe for DGCP bulk process/contract table exports.

The endpoints may return large files. The probe streams and reads only the first
small chunk so CI validates transport without downloading whole datasets.
"""
import os

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)


def _probe(path):
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
        assert first, f"DGCP bulk endpoint {path} returned an empty stream"
        print(
            f"DGCP_BULK path={path} content_type={content_type!r} "
            f"content_disposition={disposition!r} first_bytes={first[:16]!r}"
        )
        return content_type, disposition, first


def test_live_dgcp_process_and_contract_bulk_transports():
    process_type, process_disposition, process_first = _probe("/tablas/procesos")
    contract_type, contract_disposition, contract_first = _probe("/tablas/contratos")
    assert process_type or process_disposition
    assert contract_type or contract_disposition
    assert process_first
    assert contract_first
