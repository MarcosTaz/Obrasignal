"""Bounded live discovery and connector validation for Uruguay ARCE PAC.

Uses only unauthenticated same-origin public routes used by ARCE's consultation
SPA; no credentials, bypasses or hidden/private endpoints.
"""
from datetime import datetime, timezone
import os
import re
from urllib.parse import urljoin

import pytest
import requests

from uruguay_arce_pac import ARCEPACConfig, ARCEPACConnector, ARCE_PAC_TIMEZONE

PAC_PUBLIC_URL = "https://www.comprasestatales.gub.uy/consultaplananual/"
PAC_CONFIG_URL = urljoin(PAC_PUBLIC_URL, "assets/config.json")
MAX_FRONTEND_BYTES = 12 * 1024 * 1024
WORKS_FAMILY_CODE = 6
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "ObraSignal ARCE PAC public-contract probe/1.0",
    "Referer": PAC_PUBLIC_URL,
})

pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_UY_PAC") != "1",
    reason="live Uruguay PAC discovery probe is explicit opt-in only",
)


def _get(url, accept="application/json", *, params=None, raise_status=True):
    response = SESSION.get(url, params=params, headers={"Accept": accept}, timeout=45)
    if raise_status:
        response.raise_for_status()
    return response


def _frontend_contract():
    response = _get(PAC_PUBLIC_URL, "text/html,application/xhtml+xml")
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', response.text, flags=re.I)
    main_url = next((urljoin(PAC_PUBLIC_URL, value) for value in scripts if "/main." in value and value.endswith(".js")), None)
    assert main_url
    bundle = _get(main_url, "application/javascript,text/javascript,*/*;q=0.1").content
    assert 0 < len(bundle) <= MAX_FRONTEND_BYTES
    return response, main_url, bundle.decode("utf-8", errors="replace")


def _api_url():
    config = _get(PAC_CONFIG_URL).json()
    assert isinstance(config, dict)
    api_base = str(config.get("apiUrl") or "").strip().rstrip("/")
    assert api_base.startswith("/")
    resolved = urljoin(PAC_PUBLIC_URL, api_base + "/").rstrip("/")
    assert resolved.startswith("https://www.comprasestatales.gub.uy/consultaplananual")
    print("UY_PAC_API_BASE=" + api_base)
    print("UY_PAC_API_URL=" + resolved)
    return resolved


def _shape(value):
    if isinstance(value, dict):
        return "dict:" + ",".join(sorted(map(str, value.keys())))
    if isinstance(value, list):
        sample = next((row for row in value if isinstance(row, dict)), None)
        return "list:" + (",".join(sorted(map(str, sample.keys()))) if sample else "")
    return type(value).__name__


def test_live_uruguay_arce_public_pac_frontend_contract():
    response, main_url, js = _frontend_contract()
    for token in (
        "/api/v1/compra-procedimientos/",
        "/api/v1/compra-procedimientos/excel?sort=",
        "/api/v1/familias/all",
        "codFamilia", "codSubfamilia", "codClase", "codSubclase", "codArticuloServObra",
        "fechaConvocatoriaFinDesde", "fechaModificacionIni", "fechaModificacionFin",
        "./assets/config.json", "apiUrl",
    ):
        assert token in js
    position = js.find("loadProcedureQueryParameters")
    context = js[position:position + 4500]
    filter_names = []
    for name in re.findall(r'ak\([^,]+,["\']([^"\']+)["\']', context):
        if name not in filter_names:
            filter_names.append(name)
    print("UY_PAC_STATUS=" + str(response.status_code))
    print("UY_PAC_MAIN_JS=" + main_url)
    print("UY_PAC_FILTER_NAMES=" + ",".join(filter_names))
    assert "codFamilia" in filter_names
    assert "fechaConvocatoriaFinDesde" in filter_names


def test_live_uruguay_arce_public_pac_same_origin_stability_and_detail():
    api_url = _api_url()
    search_url = api_url + "/api/v1/compra-procedimientos"
    statuses = []
    successful = None
    for _ in range(3):
        response = _get(search_url, params={"sort": "id,asc", "page": 0, "size": 2}, raise_status=False)
        statuses.append(response.status_code)
        if response.status_code == 200 and "json" in response.headers.get("Content-Type", "").lower():
            successful = response
    print("UY_PAC_SEARCH_STATUSES=" + repr(statuses))
    assert statuses == [200, 200, 200], "ARCE PAC machine search is not stable across a same-origin session"
    payload = successful.json()
    print("UY_PAC_SEARCH_SHAPE=" + _shape(payload))
    assert isinstance(payload, dict) and isinstance(payload.get("content"), list)
    sample = next((row for row in payload["content"] if isinstance(row, dict)), None)
    assert sample and sample.get("id") is not None
    print("UY_PAC_PROCEDURE_FIELDS=" + ",".join(sorted(map(str, sample.keys()))))
    detail = _get(api_url + "/api/v1/compra-procedimientos/" + str(sample["id"]), raise_status=False)
    print("UY_PAC_DETAIL_STATUS=" + str(detail.status_code))
    assert detail.status_code == 200 and "json" in detail.headers.get("Content-Type", "").lower()
    detail_payload = detail.json()
    print("UY_PAC_DETAIL_SHAPE=" + _shape(detail_payload))
    if isinstance(detail_payload, dict) and isinstance(detail_payload.get("planAnual"), dict):
        print("UY_PAC_PLAN_FIELDS=" + ",".join(sorted(map(str, detail_payload["planAnual"].keys()))))


def test_live_uruguay_arce_public_pac_native_family_taxonomy_and_filter():
    api_url = _api_url()
    families = _get(api_url + "/api/v1/familias/all", raise_status=False)
    print(f"UY_PAC_FAMILIES_STATUS={families.status_code} content_type={families.headers.get('Content-Type', '')!r}")
    assert families.status_code == 200
    rows = families.json()
    assert isinstance(rows, list) and rows
    match = next((row for row in rows if isinstance(row, dict) and int(row.get("codFamilia") or -1) == WORKS_FAMILY_CODE), None)
    assert match is not None
    print("UY_PAC_WORKS_FAMILY=" + repr(match))
    assert "CONSTRUCCIONES" in str(match.get("descFamilia") or "").upper()

    response = _get(
        api_url + "/api/v1/compra-procedimientos",
        params={"sort": "periodoConvFechaIni,desc", "page": 0, "size": 5, "codFamilia": WORKS_FAMILY_CODE},
        raise_status=False,
    )
    print(f"UY_PAC_WORKS_FILTER_STATUS={response.status_code} content_type={response.headers.get('Content-Type', '')!r}")
    assert response.status_code == 200 and "json" in response.headers.get("Content-Type", "").lower()
    payload = response.json()
    assert isinstance(payload, dict) and isinstance(payload.get("content"), list)
    print("UY_PAC_WORKS_TOTAL=" + str(payload.get("totalElements")))
    print("UY_PAC_WORKS_TOTAL_PAGES=" + str(payload.get("totalPages")))
    sample = next((row for row in payload["content"] if isinstance(row, dict)), None)
    assert sample is not None
    plan = sample.get("planAnual") if isinstance(sample.get("planAnual"), dict) else {}
    print("UY_PAC_WORKS_SAMPLE_ID=" + str(sample.get("id")))
    print("UY_PAC_WORKS_SAMPLE_START=" + str(sample.get("periodoConvFechaIni")))
    print("UY_PAC_WORKS_SAMPLE_END=" + str(sample.get("periodoConvFechaFin")))
    print("UY_PAC_WORKS_SAMPLE_PLAN_YEAR=" + str(plan.get("anioPlan")))


def test_live_uruguay_arce_public_pac_future_works_bound():
    api_url = _api_url()
    search_url = api_url + "/api/v1/compra-procedimientos"
    today = datetime.now(timezone.utc).date()
    base_params = {"sort": "periodoConvFechaIni,asc", "page": 0, "size": 5, "codFamilia": WORKS_FAMILY_CODE}
    base = _get(search_url, params=base_params, raise_status=False)
    assert base.status_code == 200 and "json" in base.headers.get("Content-Type", "").lower()
    base_total = int(base.json().get("totalElements") or 0)
    assert base_total > 0

    candidates = [today.isoformat(), today.strftime("%d/%m/%Y")]
    accepted = []
    for value in candidates:
        response = _get(
            search_url,
            params={**base_params, "fechaConvocatoriaFinDesde": value},
            raise_status=False,
        )
        content_type = response.headers.get("Content-Type", "")
        record = {"value": value, "status": response.status_code, "content_type": content_type, "total": None}
        if response.status_code == 200 and "json" in content_type.lower():
            payload = response.json()
            if isinstance(payload, dict):
                record["total"] = int(payload.get("totalElements") or 0)
                rows = payload.get("content") if isinstance(payload.get("content"), list) else []
                record["rows"] = rows
        accepted.append(record)
    print("UY_PAC_FUTURE_FILTER_RESULTS=" + repr([{k: v for k, v in item.items() if k != "rows"} for item in accepted]))

    usable = [item for item in accepted if item.get("status") == 200 and item.get("total") is not None and 0 < item["total"] < base_total]
    assert usable, "ARCE PAC future-date filter did not produce a bounded subset"
    chosen = min(usable, key=lambda item: item["total"])
    print("UY_PAC_FUTURE_FILTER_CHOSEN=" + str(chosen["value"]))
    print("UY_PAC_FUTURE_TOTAL=" + str(chosen["total"]))
    for row in chosen.get("rows") or []:
        if not isinstance(row, dict):
            continue
        end = str(row.get("periodoConvFechaFin") or "")[:10]
        if end:
            assert end >= today.isoformat(), "publisher future filter returned an already-ended planned call"


def test_live_uruguay_arce_pac_connector_end_to_end():
    now = datetime.now(timezone.utc)
    connector = ARCEPACConnector(ARCEPACConfig(page_size=100, max_pages=20))
    rows = connector.fetch_snapshot(now=now)
    local_today = now.astimezone(ARCE_PAC_TIMEZONE).date().isoformat()
    print("UY_PAC_CONNECTOR_SIGNAL_COUNT=" + str(len(rows)))
    assert rows, "live PAC connector returned no future construction plans"
    assert len({row["external_id"] for row in rows}) == len(rows)
    assert all(row.get("source") == "UY_ARCE" for row in rows)
    assert all(row.get("signal_type") == "PROCUREMENT_PLAN" for row in rows)
    assert all(row.get("category_code") == "6" for row in rows)
    assert all(str(row.get("target_date") or "") >= local_today for row in rows)
    sample = rows[0]
    print("UY_PAC_CONNECTOR_SAMPLE_FIELDS=" + ",".join(sorted(map(str, sample.keys()))))
    print("UY_PAC_CONNECTOR_SAMPLE_ID=" + str(sample.get("external_id")))
    print("UY_PAC_CONNECTOR_SAMPLE_TARGET=" + str(sample.get("target_date")))
