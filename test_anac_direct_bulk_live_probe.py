"""TEMPORARY ANAC institutional-mirror probe. Delete before merge.

ANAC's own direct-download host is proven blocked by F5 from cloud. This probe
asks whether the official national/EU open-data federation physically exposes
or proxies the distribution bytes, instead of merely pointing back to ANAC.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

import requests

EU_SEARCH = "https://data.europa.eu/api/hub/search/search"
EU_DATASET = "https://data.europa.eu/api/hub/search/datasets/smartcig"
EU_DISTRIBUTIONS = "https://data.europa.eu/datasets/smartcig/distributions"
EU_PAGE = "https://data.europa.eu/data/datasets/smartcig?locale=it"
IT_PAGE = "https://www.dati.gov.it/node/view-dataset/dataset?id=20468959-2094-4f33-b6f3-c853d8edc26b"
UA = "ObraSignal ANAC institutional mirror probe/2.0"


def _record(response, limit=30000):
    ctype = (response.headers.get("content-type") or "").lower()
    body = response.text[:limit] if any(x in ctype for x in ("json", "text", "html", "xml", "rdf")) else ""
    return {
        "status": response.status_code,
        "url": response.url,
        "content_type": response.headers.get("content-type"),
        "length": len(response.content),
        "location": response.headers.get("location"),
        "prefix": body,
    }


def _urls(value, out=None):
    out = out if out is not None else []
    if isinstance(value, dict):
        for item in value.values():
            _urls(item, out)
    elif isinstance(value, list):
        for item in value:
            _urls(item, out)
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        if value not in out:
            out.append(value)
    return out


def test_anac_official_federation_mirror_live():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "*/*"})
    evidence = {"eu": {}, "it": {}, "candidate_urls": [], "candidate_fetches": []}

    requests_to_make = [
        ("search", EU_SEARCH, {"q": "smartcig", "filter": "dataset", "limit": 10}),
        ("dataset", EU_DATASET, None),
        ("distributions", EU_DISTRIBUTIONS, {"valueType": "metadata", "limit": 100}),
        ("eu_page", EU_PAGE, None),
        ("it_page", IT_PAGE, None),
    ]
    bodies = []
    for name, url, params in requests_to_make:
        r = s.get(url, params=params, timeout=60, allow_redirects=True)
        rec = _record(r)
        evidence["eu" if name != "it_page" else "it"][name] = rec
        if r.status_code == 200:
            try:
                payload = r.json()
            except Exception:
                payload = None
            if payload is not None:
                bodies.append(payload)
                rec["json_urls"] = _urls(payload)[:300]

    candidates = []
    for payload in bodies:
        for url in _urls(payload):
            low = url.lower()
            if any(token in low for token in ("smartcig", "cig_csv", "20260501", "20260401")) and url not in candidates:
                candidates.append(url)
    evidence["candidate_urls"] = candidates[:100]

    # Fetch at most 12 URLs that are not obvious metadata/landing pages. We only
    # care whether bytes are actually served by a non-ANAC institutional host.
    for url in candidates[:24]:
        host = urlparse(url).netloc.lower()
        if host in {"data.europa.eu", "www.dati.gov.it"} or "anticorruzione.it" in host:
            r = s.get(url, headers={"Range": "bytes=0-4095", "User-Agent": UA}, timeout=45, allow_redirects=True)
            evidence["candidate_fetches"].append({
                "requested": url,
                "host": host,
                "status": r.status_code,
                "final_url": r.url,
                "final_host": urlparse(r.url).netloc.lower(),
                "content_type": r.headers.get("content-type"),
                "content_range": r.headers.get("content-range"),
                "length": len(r.content),
                "magic": r.content[:8].hex(),
            })
        if len(evidence["candidate_fetches"]) >= 12:
            break

    raise AssertionError("ANAC_FEDERATION_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
