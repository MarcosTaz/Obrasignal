"""TEMPORARY live discovery probe for Austria BVergG Kerndaten.

The former CKAN-looking path was proved absent. This second probe inspects only
the official data.gv.at frontend and a bounded set of its own JavaScript bundles
to discover the catalogue backend used by the current SPA. Remove before merge.
"""
from urllib.parse import urljoin, urlparse
import json
import re

import requests

ROOT = "https://www.data.gv.at/"
CATALOG_PAGE = "https://www.data.gv.at/katalog/"
HEADERS = {
    "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.8",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}


def _scripts(html_text, base_url):
    found = []
    for match in re.finditer(r"<script[^>]+src=[\"']([^\"']+)[\"']", html_text or "", re.I):
        url = urljoin(base_url, match.group(1))
        if url not in found:
            found.append(url)
    return found


def _links(html_text, base_url):
    found = []
    for match in re.finditer(r"<link[^>]+href=[\"']([^\"']+)[\"']", html_text or "", re.I):
        url = urljoin(base_url, match.group(1))
        if url not in found:
            found.append(url)
    return found


def _interesting_snippets(text):
    text = str(text or "")
    snippets = []
    patterns = (
        r"https?://[^\"'\s)\\]{4,220}",
        r"/[A-Za-z0-9_.~/-]{0,90}(?:api|search|dataset|catalog|katalog)[A-Za-z0-9_?=&.%~:/-]{0,140}",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = match.group(0)
            lowered = value.lower()
            if not any(token in lowered for token in ("api", "search", "dataset", "catalog", "katalog", "data.gv.at")):
                continue
            value = value[:260]
            if value not in snippets:
                snippets.append(value)
            if len(snippets) >= 80:
                return snippets
    return snippets


def test_austria_official_catalogue_frontend_discovery_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {"pages": {}, "bundles": []}
    scripts = []

    for url in (ROOT, CATALOG_PAGE):
        response = session.get(url, timeout=45, allow_redirects=True)
        page_scripts = _scripts(response.text, response.url)
        for item in page_scripts:
            if item not in scripts:
                scripts.append(item)
        evidence["pages"][url] = {
            "status": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get("content-type"),
            "bytes": len(response.content),
            "title": (re.search(r"<title[^>]*>(.*?)</title>", response.text, re.I | re.S).group(1).strip()
                      if re.search(r"<title[^>]*>(.*?)</title>", response.text, re.I | re.S) else None),
            "scripts": page_scripts[:20],
            "links": _links(response.text, response.url)[:30],
            "html_snippets": _interesting_snippets(response.text)[:30],
        }

    official_host = urlparse(ROOT).hostname
    bounded_scripts = [
        url for url in scripts
        if urlparse(url).hostname == official_host and urlparse(url).path.lower().endswith((".js", ".mjs"))
    ][:8]

    for url in bounded_scripts:
        response = session.get(url, timeout=45)
        text = response.text[:1_500_000]
        evidence["bundles"].append({
            "url": url,
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "bytes": len(response.content),
            "interesting": _interesting_snippets(text),
        })

    raise AssertionError(
        "AT_KERNDATEN_FRONTEND_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000]
    )
