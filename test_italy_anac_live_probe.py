"""TEMPORARY live probe for Italy ANAC BDNCP open-data contract.

Delete before merge. This intentionally fails after printing bounded evidence.
"""
from datetime import datetime, timezone
import json

import requests


HEADERS = {
    "Accept": "application/json,text/html;q=0.8,*/*;q=0.5",
    "User-Agent": "ObraSignal ANAC live validation/1.0",
}


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def _resource_summary(resource):
    return {
        key: resource.get(key)
        for key in (
            "id", "name", "format", "url", "size", "last_modified",
            "created", "mimetype", "resource_type", "license_type",
        )
        if resource.get(key) is not None
    }


def test_italy_anac_catalog_and_delta_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {"at": datetime.now(timezone.utc).isoformat(), "catalog_candidates": {}}

    candidates = [
        "https://dati.anticorruzione.it/api/3/action/package_search",
        "https://dati.anticorruzione.it/opendata/api/3/action/package_search",
    ]
    chosen = None
    payload = None
    for endpoint in candidates:
        response = session.get(endpoint, params={"q": "CIG aggiornamenti delta", "rows": 10}, timeout=45)
        parsed = _safe_json(response)
        evidence["catalog_candidates"][endpoint] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "final_url": response.url,
            "body_prefix": response.text[:500],
        }
        if response.status_code == 200 and isinstance(parsed, dict) and parsed.get("success") is True:
            chosen, payload = endpoint, parsed
            break

    evidence["chosen_catalog"] = chosen
    results = []
    if payload:
        result = payload.get("result") or {}
        for package in result.get("results") or []:
            resources = package.get("resources") or []
            results.append({
                "id": package.get("id"),
                "name": package.get("name"),
                "title": package.get("title"),
                "license_id": package.get("license_id"),
                "license_title": package.get("license_title"),
                "metadata_modified": package.get("metadata_modified"),
                "resources": [_resource_summary(r) for r in resources[-12:]],
            })
    evidence["packages"] = results

    # Inspect the most recently modified JSON delta resource without downloading
    # a large archive. HEAD plus a tiny range request is enough to prove public
    # machine access and file type/redirect behavior.
    json_resources = []
    for package in results:
        if "aggiornamenti" not in str(package.get("title", "")).lower() and "delta" not in str(package.get("title", "")).lower():
            continue
        for resource in package.get("resources", []):
            if str(resource.get("format", "")).upper() == "JSON" and resource.get("url"):
                json_resources.append(resource)
    json_resources.sort(key=lambda r: str(r.get("last_modified") or r.get("created") or ""), reverse=True)

    if json_resources:
        resource = json_resources[0]
        url = resource["url"]
        head = session.head(url, timeout=45, allow_redirects=True)
        tiny = session.get(url, headers={**HEADERS, "Range": "bytes=0-2047"}, timeout=45, allow_redirects=True)
        evidence["latest_json_delta"] = {
            "resource": resource,
            "head": {
                "status": head.status_code,
                "final_url": head.url,
                "content_type": head.headers.get("content-type"),
                "content_length": head.headers.get("content-length"),
                "accept_ranges": head.headers.get("accept-ranges"),
            },
            "range": {
                "status": tiny.status_code,
                "final_url": tiny.url,
                "content_type": tiny.headers.get("content-type"),
                "content_range": tiny.headers.get("content-range"),
                "bytes_received": len(tiny.content),
                "prefix_hex": tiny.content[:24].hex(),
            },
        }

    raise AssertionError("IT_ANAC_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000])
