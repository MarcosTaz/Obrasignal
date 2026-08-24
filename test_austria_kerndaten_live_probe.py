"""TEMPORARY live discovery probe for Austria BVergG Kerndaten.

This probe only interrogates Austria's official open-data catalogue to discover
publisher datasets/resources. It is intentionally removed before permanent CI.
"""
from urllib.parse import urlparse
import json

import requests

CATALOG = "https://www.data.gv.at/katalog/api/3/action/package_search"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}


def _resource_summary(resource):
    if not isinstance(resource, dict):
        return None
    url = str(resource.get("url") or "")
    return {
        "name": resource.get("name"),
        "format": resource.get("format"),
        "mimetype": resource.get("mimetype"),
        "url": url,
        "host": urlparse(url).hostname if url else None,
    }


def _dataset_summary(dataset):
    if not isinstance(dataset, dict):
        return None
    resources = [
        item for item in (_resource_summary(resource) for resource in dataset.get("resources") or [])
        if item
    ]
    return {
        "id": dataset.get("id"),
        "name": dataset.get("name"),
        "title": dataset.get("title"),
        "organization": (dataset.get("organization") or {}).get("title") if isinstance(dataset.get("organization"), dict) else None,
        "license_id": dataset.get("license_id"),
        "license_title": dataset.get("license_title"),
        "metadata_modified": dataset.get("metadata_modified"),
        "notes_prefix": str(dataset.get("notes") or "")[:800],
        "resources": resources[:20],
    }


def test_austria_official_catalogue_kerndaten_discovery_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {}

    for term in ("Kerndaten", "BVergG", "Vergabe", "Bekanntmachung"):
        response = session.get(CATALOG, params={"q": term, "rows": 20}, timeout=45)
        payload = None
        try:
            payload = response.json()
        except Exception:
            pass
        result = payload.get("result") if isinstance(payload, dict) else None
        datasets = result.get("results") if isinstance(result, dict) else None
        evidence[term] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "url": response.url,
            "success": payload.get("success") if isinstance(payload, dict) else None,
            "count": result.get("count") if isinstance(result, dict) else None,
            "datasets": [
                item for item in (_dataset_summary(dataset) for dataset in (datasets or [])[:20])
                if item
            ],
            "body_prefix": response.text[:1200] if payload is None else None,
        }

    raise AssertionError(
        "AT_KERNDATEN_CATALOG_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000]
    )
