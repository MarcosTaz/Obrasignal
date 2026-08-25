"""Explicit bounded discovery probe for Uruguay ARCE public annual procurement plans.

Research-only until a stable public machine contract is proven. The probe reads
only the unauthenticated public PAC page and its public frontend bundle, records
literal data-route evidence, and never submits credentials or bypasses controls.
"""
import os
import re
from urllib.parse import urljoin

import pytest
import requests


PAC_PUBLIC_URL = "https://www.comprasestatales.gub.uy/consultaplananual/"
MAX_FRONTEND_BYTES = 12 * 1024 * 1024

pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_UY_PAC") != "1",
    reason="live Uruguay PAC discovery probe is explicit opt-in only",
)


def _interesting(values):
    found = []
    for value in values:
        text = str(value or "").strip()
        lowered = text.lower()
        if any(token in lowered for token in ("plan", "excel", "xlsx", "xls", "api", "ajax", "consulta", "buscar")):
            absolute = urljoin(PAC_PUBLIC_URL, text)
            if absolute not in found:
                found.append(absolute)
    return found


def _public_get(url, accept):
    response = requests.get(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "ObraSignal ARCE PAC public-contract probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    return response


def test_live_uruguay_arce_public_pac_surface_contract():
    response = _public_get(PAC_PUBLIC_URL, "text/html,application/xhtml+xml")
    text = response.text
    assert text, "ARCE PAC public search returned an empty document"

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I)
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, flags=re.I)
    actions = re.findall(r'<form[^>]+action=["\']([^"\']*)["\']', text, flags=re.I)

    script_urls = [urljoin(PAC_PUBLIC_URL, value) for value in scripts]
    main_url = next((url for url in script_urls if "/main." in url and url.endswith(".js")), None)
    assert main_url, "ARCE PAC public SPA did not expose a main frontend bundle"

    bundle_response = _public_get(main_url, "application/javascript,text/javascript,*/*;q=0.1")
    bundle = bundle_response.content
    assert 0 < len(bundle) <= MAX_FRONTEND_BYTES, "ARCE PAC frontend bundle exceeded bounded research cap"
    js = bundle.decode("utf-8", errors="replace")

    # Extract URL/route-like string literals only. Do not log arbitrary script
    # source or data values.
    literals = re.findall(r'["\']([^"\']{2,300})["\']', js)
    route_literals = []
    for literal in literals:
        lowered = literal.lower()
        if not any(token in lowered for token in ("plan", "excel", "xlsx", "api", "consulta", "buscar")):
            continue
        if not any(marker in literal for marker in ("/", "http", ".xls", ".xlsx")):
            continue
        if literal not in route_literals:
            route_literals.append(literal)

    print("UY_PAC_STATUS=" + str(response.status_code))
    print("UY_PAC_INTERESTING_HREFS=" + " | ".join(_interesting(hrefs)[:80]))
    print("UY_PAC_INTERESTING_SCRIPTS=" + " | ".join(_interesting(scripts)[:80]))
    print("UY_PAC_INTERESTING_FORMS=" + " | ".join(_interesting(actions)[:80]))
    print("UY_PAC_MAIN_JS=" + main_url)
    print("UY_PAC_ROUTE_LITERALS=" + " | ".join(route_literals[:120]))

    assert response.url.startswith("https://www.comprasestatales.gub.uy/")
