"""Explicit bounded live probe for PanamaCompraenCifras V2.

This is research evidence only. It intentionally does not guess undocumented API
endpoints or bypass access controls.
"""
import os
import re

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_PANAMA") != "1",
    reason="live Panama probe is explicit opt-in only",
)

ROOT = "https://v2.panamacompraencifras.gob.pa/"
API_PAGE = "https://v2.panamacompraencifras.gob.pa/api"
DOWNLOADS_PAGE = "https://v2.panamacompraencifras.gob.pa/descargas"


def _get(url):
    return requests.get(
        url,
        headers={
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "User-Agent": "ObraSignal Panama public contract probe/1.0",
        },
        timeout=45,
        allow_redirects=True,
    )


def test_live_panama_v2_public_contract_surfaces():
    root = _get(ROOT)
    root.raise_for_status()
    text = root.text
    assert "PanamaCompra" in text or "panamacompra" in text.lower()

    api = _get(API_PAGE)
    api.raise_for_status()
    downloads = _get(DOWNLOADS_PAGE)
    downloads.raise_for_status()

    combined = "\n".join((text, api.text, downloads.text))
    assert re.search(r"OCDS|Open Contracting|Contrataciones Abiertas", combined, re.I)

    # Record only discoverable public URLs. The probe deliberately does not
    # synthesize API paths from frontend JavaScript.
    urls = sorted(set(re.findall(r"https?://[^\"'<>\\s]+", combined)))
    machine_candidates = [
        url.rstrip(")],;\"")
        for url in urls
        if any(token in url.lower() for token in ("api", "swagger", "openapi", "json", "download"))
    ]
    print("PANAMA_MACHINE_CANDIDATES=" + repr(machine_candidates[:50]))
    assert api.url.startswith("https://v2.panamacompraencifras.gob.pa/")
    assert downloads.url.startswith("https://v2.panamacompraencifras.gob.pa/")
