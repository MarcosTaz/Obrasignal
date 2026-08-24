"""TEMPORARY live probe for Austria distributed KDQ accessibility and eForms discovery.

Delete before merge. Intentionally fails after printing bounded evidence.
"""
from datetime import datetime, timezone
import json
from urllib.parse import urlparse

import requests


CATALOG = "https://www.data.gv.at"
HEADERS = {
    "Accept": "application/json,application/ld+json;q=0.9,application/xml;q=0.8,*/*;q=0.5",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
MAX_DATASETS = 20
MAX_KDQ_PREFIX = 8192


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def _graph_access_urls(payload):
    out = []
    if not isinstance(payload, dict):
        return out
    for node in payload.get("@graph") or []:
        if not isinstance(node, dict):
            continue
        access = node.get("dcat:accessURL")
        if isinstance(access, dict):
            value = str(access.get("@id") or "").strip()
            if value and value not in out:
                out.append(value)
    return out


def _catalog_search(session, query, limit=MAX_DATASETS):
    r = session.get(
        f"{CATALOG}/api/hub/search/search",
        params={"q": query, "limit": limit},
        timeout=45,
    )
    r.raise_for_status()
    payload = r.json()
    result = payload.get("result") or {}
    rows = result.get("results") or []
    return int(result.get("count") or 0), [row for row in rows if isinstance(row, dict)]


def _dataset_access_urls(session, dataset_id):
    r = session.get(
        f"{CATALOG}/api/hub/repo/datasets/{dataset_id}",
        headers={**HEADERS, "Accept": "application/ld+json"},
        timeout=45,
    )
    r.raise_for_status()
    return _graph_access_urls(r.json()), r.status_code


def _probe_kdq(session, url):
    result = {"url": url, "host": urlparse(url).hostname}
    try:
        r = session.get(url, headers={**HEADERS, "Accept": "application/xml,text/xml,*/*"}, timeout=20, stream=True, allow_redirects=True)
        result.update({
            "status": r.status_code,
            "final_url": r.url,
            "content_type": r.headers.get("content-type"),
            "content_length": r.headers.get("content-length"),
        })
        prefix = bytearray()
        try:
            for chunk in r.iter_content(2048):
                if chunk:
                    prefix.extend(chunk)
                if len(prefix) >= MAX_KDQ_PREFIX:
                    break
        finally:
            r.close()
        result["prefix_bytes"] = len(prefix)
        result["prefix"] = bytes(prefix[:2000]).decode("utf-8", errors="replace")
    except requests.RequestException as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
    return result


def _result_summary(row):
    title = row.get("title")
    if isinstance(title, dict):
        title = title.get("de") or title.get("en") or next(iter(title.values()), "")
    return {
        "id": row.get("id"),
        "title": title,
        "modified": row.get("modified"),
        "issued": row.get("issued"),
        "publisher": row.get("publisher"),
        "distributions": [
            {
                "id": d.get("id"),
                "format": d.get("format"),
                "media_type": d.get("media_type"),
                "modified": d.get("modified"),
                "license": d.get("license"),
            }
            for d in (row.get("distributions") or [])[:3]
            if isinstance(d, dict)
        ],
    }


def test_austria_distributed_kdq_accessibility_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {"at": datetime.now(timezone.utc).isoformat(), "queries": {}, "kdqs": []}

    discovered = []
    for query in ("Kerndaten", "Ausschreibung", "eForms", "eforms Vergabe"):
        try:
            count, rows = _catalog_search(session, query)
            evidence["queries"][query] = {
                "count": count,
                "rows": [_result_summary(row) for row in rows[:10]],
            }
            if query in ("Kerndaten", "Ausschreibung"):
                for row in rows:
                    dataset_id = str(row.get("id") or "").strip()
                    if dataset_id and dataset_id not in discovered:
                        discovered.append(dataset_id)
        except requests.RequestException as exc:
            evidence["queries"][query] = {"error": f"{type(exc).__name__}: {str(exc)[:400]}"}

    for dataset_id in discovered[:MAX_DATASETS]:
        row = {"dataset_id": dataset_id}
        try:
            urls, status = _dataset_access_urls(session, dataset_id)
            row["metadata_status"] = status
            row["access_urls"] = urls
            row["probes"] = [_probe_kdq(session, url) for url in urls[:2]]
        except requests.RequestException as exc:
            row["metadata_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        evidence["kdqs"].append(row)

    raise AssertionError("AT_KERNDATEN_DISTRIBUTED_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:80000])
