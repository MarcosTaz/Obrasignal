"""Explicit bounded discovery probe for Uruguay ARCE public annual procurement plans.

Research-only until a stable public machine contract and structured works
admission are proven. The probe uses only unauthenticated assets/routes used by
ARCE's own public PAC consultation SPA. It never submits credentials or bypasses
controls.
"""
import os
import re
from urllib.parse import urljoin

import pytest
import requests


PAC_PUBLIC_URL = "https://www.comprasestatales.gub.uy/consultaplananual/"
PAC_CONFIG_URL = urljoin(PAC_PUBLIC_URL, "assets/config.json")
MAX_FRONTEND_BYTES = 12 * 1024 * 1024

pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_UY_PAC") != "1",
    reason="live Uruguay PAC discovery probe is explicit opt-in only",
)


def _public_get(url, accept, *, raise_status=True, params=None, stream=False):
    response = requests.get(
        url,
        params=params,
        headers={
            "Accept": accept,
            "User-Agent": "ObraSignal ARCE PAC public-contract probe/1.0",
        },
        timeout=45,
        stream=stream,
    )
    if raise_status:
        response.raise_for_status()
    return response


def _frontend_contract():
    response = _public_get(PAC_PUBLIC_URL, "text/html,application/xhtml+xml")
    text = response.text
    assert text, "ARCE PAC public search returned an empty document"
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, flags=re.I)
    script_urls = [urljoin(PAC_PUBLIC_URL, value) for value in scripts]
    main_url = next((url for url in script_urls if "/main." in url and url.endswith(".js")), None)
    assert main_url, "ARCE PAC public SPA did not expose a main frontend bundle"
    bundle_response = _public_get(main_url, "application/javascript,text/javascript,*/*;q=0.1")
    bundle = bundle_response.content
    assert 0 < len(bundle) <= MAX_FRONTEND_BYTES, "ARCE PAC frontend bundle exceeded bounded research cap"
    return response, main_url, bundle.decode("utf-8", errors="replace")


def _api_route_literals(js):
    values = []
    for value in re.findall(r'["\'](/api/v1/[^"\']{1,220})["\']', js):
        if value not in values:
            values.append(value)
    return values


def test_live_uruguay_arce_public_pac_frontend_contract():
    response, main_url, js = _frontend_contract()
    assert "/api/v1/compra-procedimientos/" in js
    assert "/api/v1/compra-procedimientos/excel?sort=" in js
    assert "./assets/config.json" in js
    assert "apiUrl" in js
    routes = _api_route_literals(js)
    relevant = [
        route for route in routes
        if any(token in route.lower() for token in (
            "compra-proced", "articulo", "famil", "clase", "subclase", "catalog", "item"
        ))
    ]
    print("UY_PAC_STATUS=" + str(response.status_code))
    print("UY_PAC_MAIN_JS=" + main_url)
    print("UY_PAC_FRONTEND_CONTRACT=search,detail,excel,pagination,public-config")
    print("UY_PAC_RELEVANT_API_ROUTES=" + " | ".join(relevant[:120]))


def _shape(value):
    if isinstance(value, dict):
        return "dict:" + ",".join(sorted(map(str, value.keys())))
    if isinstance(value, list):
        sample = next((row for row in value if isinstance(row, dict)), None)
        return "list:" + (",".join(sorted(map(str, sample.keys()))) if sample else "")
    return type(value).__name__


def _configured_api_url():
    config_response = _public_get(PAC_CONFIG_URL, "application/json")
    config = config_response.json()
    assert isinstance(config, dict)
    api_base = str(config.get("apiUrl") or "").strip().rstrip("/")
    assert api_base.startswith("/"), "ARCE PAC public config changed apiUrl semantics"
    api_url = urljoin(PAC_PUBLIC_URL, api_base + "/").rstrip("/")
    assert api_url.startswith("https://www.comprasestatales.gub.uy/consultaplananual")
    print("UY_PAC_CONFIG_KEYS=" + ",".join(sorted(map(str, config.keys()))))
    print("UY_PAC_API_BASE=" + api_base)
    print("UY_PAC_API_URL=" + api_url)
    return api_url


def test_live_uruguay_arce_public_pac_backend_contract():
    api_url = _configured_api_url()
    search_url = api_url + "/api/v1/compra-procedimientos"
    response = _public_get(
        search_url,
        "application/json",
        raise_status=False,
        params={"sort": "id,asc", "page": 0, "size": 2},
    )
    content_type = response.headers.get("Content-Type", "")
    print(f"UY_PAC_REAL_API_STATUS={response.status_code} content_type={content_type!r}")
    assert response.status_code == 200, "ARCE PAC configured public API is not anonymously readable"
    assert "json" in content_type.lower(), "ARCE PAC configured search route is not JSON"
    payload = response.json()
    print("UY_PAC_REAL_API_SHAPE=" + _shape(payload))
    assert isinstance(payload, dict)
    content = payload.get("content")
    assert isinstance(content, list)
    sample = next((row for row in content if isinstance(row, dict)), None)
    assert sample is not None
    print("UY_PAC_PROCEDURE_FIELDS=" + ",".join(sorted(map(str, sample.keys()))))

    procedure_id = sample.get("id")
    assert procedure_id is not None
    detail = _public_get(
        api_url + "/api/v1/compra-procedimientos/" + str(procedure_id),
        "application/json",
        raise_status=False,
    )
    detail_type = detail.headers.get("Content-Type", "")
    print(f"UY_PAC_DETAIL_STATUS={detail.status_code} content_type={detail_type!r}")
    assert detail.status_code == 200
    assert "json" in detail_type.lower()
    detail_payload = detail.json()
    print("UY_PAC_DETAIL_SHAPE=" + _shape(detail_payload))
    if isinstance(detail_payload, dict):
        for key, value in detail_payload.items():
            if isinstance(value, (dict, list)):
                print(f"UY_PAC_DETAIL_{str(key).upper()}_SHAPE=" + _shape(value))

    # The SPA advertises an Excel export, but current production returned 404 on
    # the literal route. Keep that negative evidence without making it a source
    # gate: paginated JSON is the candidate ingestion transport.
    export_url = api_url + "/api/v1/compra-procedimientos/excel"
    with _public_get(
        export_url,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.1",
        raise_status=False,
        params={"sort": "id,asc"},
        stream=True,
    ) as export_response:
        export_type = export_response.headers.get("Content-Type", "")
        print(f"UY_PAC_EXPORT_STATUS={export_response.status_code} content_type={export_type!r}")
        assert export_response.status_code < 500, "ARCE PAC export route is server-failing"
