"""TEMPORARY live contract probe for Austria BVergG Kerndaten.

The official portal is a Piveau SPA. Official OpenAPI is exposed under the
quality-system hub, and public dataset pages provide real BVergG dataset IDs.
This probe tests the corresponding read-only Piveau search/resource contracts
on production and QS, then records the exact machine-readable metadata shape.
Remove before merge.
"""
import json

import requests

HEADERS = {
    "Accept": "application/json,application/ld+json;q=0.9,*/*;q=0.5",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
HOSTS = ("https://www.data.gv.at", "https://qs.data.gv.at")
KNOWN_BVERGG_DATASET = "78b227dc-78f6-4085-b4fb-772e040a14e0"  # AUSSCHREIBUNG.AT public dataset page


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def _shape(value, depth=0):
    if depth > 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _shape(v, depth + 1) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1)] if value else []
    return type(value).__name__


def _interesting(value, path="", out=None):
    if out is None:
        out = []
    if len(out) >= 120:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            low = str(key).lower()
            if any(token in low for token in (
                "title", "description", "label", "distribution", "access", "download",
                "license", "format", "media", "resource", "publisher", "modified",
                "issued", "identifier", "id", "url",
            )) and not isinstance(child, (dict, list)):
                out.append((child_path, child))
            _interesting(child, child_path, out)
    elif isinstance(value, list):
        for index, child in enumerate(value[:10]):
            _interesting(child, f"{path}[{index}]", out)
    return out


def _record(response):
    payload = _safe_json(response)
    return {
        "status": response.status_code,
        "final_url": response.url,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
        "shape": _shape(payload) if payload is not None else None,
        "interesting": _interesting(payload) if payload is not None else [],
        "body_prefix": None if payload is not None else response.text[:2500],
    }


def test_austria_piveau_read_contract_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {}

    for host in HOSTS:
        host_evidence = {}

        # Frontend dataset service contract observed in the official SPA bundle:
        # baseUrl + "search" with result/count/results.
        for search_base in (f"{host}/api/hub/search/", f"{host}/api/hub/search"):
            try:
                response = session.get(
                    search_base.rstrip("/") + "/search",
                    params={"q": "Kerndaten", "limit": 10},
                    timeout=45,
                    allow_redirects=True,
                )
                host_evidence[f"search:{search_base}"] = _record(response)
            except requests.RequestException as exc:
                host_evidence[f"search:{search_base}"] = {"error": type(exc).__name__}

        # hub-repo OpenAPI exposes resources/{type}/{id}; the SPA uses
        # resources/datasets/{datasetId} with application/ld+json.
        resource_url = f"{host}/api/hub/repo/resources/datasets/{KNOWN_BVERGG_DATASET}"
        try:
            response = session.get(
                resource_url,
                params={"useNormalizedId": "true", "locale": "de"},
                headers={**HEADERS, "Accept": "application/ld+json"},
                timeout=45,
                allow_redirects=True,
            )
            host_evidence["dataset_resource"] = _record(response)
        except requests.RequestException as exc:
            host_evidence["dataset_resource"] = {"error": type(exc).__name__}

        # Also test direct dataset metadata endpoint from the same official
        # OpenAPI; this is read-only and useful if resource JSON-LD differs.
        dataset_url = f"{host}/api/hub/repo/datasets/{KNOWN_BVERGG_DATASET}"
        try:
            response = session.get(
                dataset_url,
                headers={**HEADERS, "Accept": "application/ld+json"},
                timeout=45,
                allow_redirects=True,
            )
            host_evidence["dataset"] = _record(response)
        except requests.RequestException as exc:
            host_evidence["dataset"] = {"error": type(exc).__name__}

        evidence[host] = host_evidence

    raise AssertionError(
        "AT_KERNDATEN_PIVEAU_CONTRACT_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000]
    )
