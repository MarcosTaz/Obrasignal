"""Bounded live probe for DGCP bulk exports and partition discovery.

Full historical process XLSX exceeds the bounded probe budget, so production
must not blindly download it. This probe validates the official bulk transport
and discovers publisher-exposed partition links from the official tables page.
"""
import os
import re
from urllib.parse import urljoin

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)

TABLES_PAGE = "https://datosabiertos.dgcp.gob.do/datos-abiertos/tablas"


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
        print(
            f"DGCP_BULK path={path} content_type={content_type!r} "
            f"content_disposition={disposition!r} first_bytes={first[:16]!r}"
        )
        return content_type, disposition


def test_live_dgcp_bulk_transports_and_partition_links():
    process_type, process_disposition = _probe_transport("/tablas/procesos")
    contract_type, contract_disposition = _probe_transport("/tablas/contratos")
    assert process_type or process_disposition
    assert contract_type or contract_disposition

    response = requests.get(
        TABLES_PAGE,
        headers={"User-Agent": "ObraSignal DGCP partition discovery probe/1.0"},
        timeout=45,
    )
    response.raise_for_status()
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', response.text, flags=re.IGNORECASE)
    links = []
    seen = set()
    for href in hrefs:
        absolute = urljoin(TABLES_PAGE, href)
        lowered = absolute.lower()
        if "2026" not in lowered:
            continue
        if not any(token in lowered for token in ("proceso", "contrato", "csv", "xlsx", "tabla")):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    print("DGCP_2026_PARTITION_LINKS=" + " | ".join(links[:50]))
    assert links, "DGCP tables page exposes no discoverable 2026 partition links"
