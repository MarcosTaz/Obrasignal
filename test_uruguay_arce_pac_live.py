"""Explicit bounded discovery probe for Uruguay ARCE public annual procurement plans.

This is research-only until a stable public machine contract is proven. The test
uses only the unauthenticated public PAC search page, records structural links and
forms, and never submits credentials or bypasses UI/security controls.
"""
import os
import re
from urllib.parse import urljoin

import pytest
import requests


PAC_PUBLIC_URL = "https://www.comprasestatales.gub.uy/consultaplananual/"

pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_UY_PAC") != "1",
    reason="live Uruguay PAC discovery probe is explicit opt-in only",
)


def _interesting(values):
    found = []
    for value in values:
        text = str(value or "").strip()
        lowered = text.lower()
        if any(token in lowered for token in ("plan", "excel", "xlsx", "xls", "api", "ajax", "consulta")):
            absolute = urljoin(PAC_PUBLIC_URL, text)
            if absolute not in found:
                found.append(absolute)
    return found


def test_live_uruguay_arce_public_pac_surface_contract():
    response = requests.get(
        PAC_PUBLIC_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "ObraSignal ARCE PAC public-contract probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    text = response.text
    assert text, "ARCE PAC public search returned an empty document"

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I)
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, flags=re.I)
    actions = re.findall(r'<form[^>]+action=["\']([^"\']*)["\']', text, flags=re.I)

    links = _interesting(hrefs)
    script_links = _interesting(scripts)
    form_actions = _interesting(actions)

    print("UY_PAC_STATUS=" + str(response.status_code))
    print("UY_PAC_INTERESTING_HREFS=" + " | ".join(links[:80]))
    print("UY_PAC_INTERESTING_SCRIPTS=" + " | ".join(script_links[:80]))
    print("UY_PAC_INTERESTING_FORMS=" + " | ".join(form_actions[:80]))
    print("UY_PAC_HAS_EXCEL_TEXT=" + str("excel" in text.lower()))
    print("UY_PAC_HAS_SERVER_ERROR_TEXT=" + str("error de comunicación con el servidor" in text.lower()))

    # Public surface must remain reachable. Discovery of a stable data route is
    # evaluated from the logged structure before any implementation is approved.
    assert response.url.startswith("https://www.comprasestatales.gub.uy/")
