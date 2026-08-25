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
PAC_API_ROOT = "https://www.comprasestatales.gub.uy/api/v1"
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


def _public_get(url, accept, *, raise_status=True, params=None):
    response = requests.get(
        url,
        params=params,
        headers={
            "Accept": accept,
            "User-Agent": "ObraSignal ARCE PAC public-contract probe/1.0",
        },
        timeout=45,
    )
    if raise_status:
        response.raise_for_status()
    return response


def _frontend_contract():
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
    return response, hrefs, scripts, actions, main_url, bundle.decode("utf-8", errors="replace")


def test_live_uruguay_arce_public_pac_surface_contract():
    response, hrefs, scripts, actions, main_url, js = _frontend_contract()

    literals = re.findall(r'["\']([^"\']{2,300})["\']', js)
    route_literals = []
    config_literals = []
    for literal in literals:
        lowered = literal.lower()
        if any(token in lowered for token in ("plan", "excel", "xlsx", "api", "consulta", "buscar")) and any(
            marker in literal for marker in ("/", "http", ".xls", ".xlsx")
        ):
            if literal not in route_literals:
                route_literals.append(literal)
        if (
            literal.startswith("http")
            or any(token in lowered for token in ("backend", "baseurl", "apiurl", "serverurl", "urlbackend", "environment"))
        ) and literal not in config_literals:
            config_literals.append(literal)

    print("UY_PAC_STATUS=" + str(response.status_code))
    print("UY_PAC_INTERESTING_HREFS=" + " | ".join(_interesting(hrefs)[:80]))
    print("UY_PAC_INTERESTING_SCRIPTS=" + " | ".join(_interesting(scripts)[:80]))
    print("UY_PAC_INTERESTING_FORMS=" + " | ".join(_interesting(actions)[:80]))
    print("UY_PAC_MAIN_JS=" + main_url)
    print("UY_PAC_ROUTE_LITERALS=" + " | ".join(route_literals[:120]))
    print("UY_PAC_CONFIG_LITERALS=" + " | ".join(config_literals[:120]))

    for needle, label in (
        ("/api/v1/compra-procedimientos/", "PROCEDURE"),
        ("/api/v1/util/get-header", "UTIL"),
    ):
        position = js.find(needle)
        assert position >= 0
        context = re.sub(r"\s+", " ", js[max(0, position - 700): position + 900])
        print(f"UY_PAC_{label}_CONTEXT=" + context)

    # Find bounded contexts where Angular HttpClient-style calls are constructed;
    # useful to identify whether RestService prefixes an environment host.
    for needle in ("http.get", ".http.get", "baseUrl", "urlBackend", "apiUrl"):
        position = js.find(needle)
        if position >= 0:
            context = re.sub(r"\s+", " ", js[max(0, position - 500): position + 700])
            print("UY_PAC_HTTP_CONTEXT=" + context)
            break

    assert response.url.startswith("https://www.comprasestatales.gub.uy/")


def _shape(value):
    if isinstance(value, dict):
        return "dict:" + ",".join(sorted(map(str, value.keys())))
    if isinstance(value, list):
        sample = next((row for row in value if isinstance(row, dict)), None)
        return "list:" + (",".join(sorted(map(str, sample.keys()))) if sample else "")
    return type(value).__name__


def test_live_uruguay_arce_public_pac_api_candidate():
    url = f"{PAC_API_ROOT}/compra-procedimientos/"
    response = _public_get(url, "application/json", raise_status=False)
    content_type = response.headers.get("Content-Type", "")
    print(f"UY_PAC_API_STATUS={response.status_code} content_type={content_type!r}")
    if "json" in content_type.lower():
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if payload is not None:
            print("UY_PAC_API_SHAPE=" + _shape(payload))
            if isinstance(payload, dict):
                for key in ("content", "data", "results", "items"):
                    nested = payload.get(key)
                    if nested is not None:
                        print(f"UY_PAC_API_{key.upper()}_SHAPE=" + _shape(nested))
    assert response.status_code < 500, "ARCE PAC API candidate is server-failing"
