"""TEMPORARY live discovery probe for Austria BVergG Kerndaten.

The former CKAN-looking path was proved absent. This probe inspects the current
official data.gv.at SPA bundle with strict string extraction to discover the
actual backend contract. Remove before merge.
"""
from urllib.parse import urljoin, urlparse
import json
import re
import string

import requests

ROOT = "https://www.data.gv.at/"
HEADERS = {
    "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.8",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
TOKENS = ("baseurl", "axios", "fetch(", "dataset", "datasets", "search", "catalog", "katalog", "api/")


def _scripts(html_text, base_url):
    found = []
    for match in re.finditer(r"<script[^>]+src=[\"']([^\"']+)[\"']", html_text or "", re.I):
        url = urljoin(base_url, match.group(1))
        if url not in found:
            found.append(url)
    return found


def _printable(value):
    return bool(value) and all(ch in string.printable or ord(ch) >= 160 for ch in value)


def _http_urls(text):
    found = []
    for match in re.finditer(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]{4,260}", text or ""):
        value = match.group(0).rstrip(".,;:)")
        if value not in found:
            found.append(value)
        if len(found) >= 120:
            break
    return found


def _quoted_candidates(text):
    found = []
    # Keep only short quoted strings; this avoids random minified/base64 spans.
    for match in re.finditer(r"[\"']([^\"'\\\n\r]{3,260})[\"']", text or ""):
        value = match.group(1)
        lowered = value.lower()
        if not _printable(value):
            continue
        if not any(token in lowered for token in ("api", "dataset", "search", "catalog", "katalog", "data.gv.at")):
            continue
        if value not in found:
            found.append(value)
        if len(found) >= 120:
            break
    return found


def _contexts(text):
    lowered = (text or "").lower()
    found = []
    for token in TOKENS:
        start = 0
        while True:
            pos = lowered.find(token, start)
            if pos < 0:
                break
            left = max(0, pos - 180)
            right = min(len(text), pos + len(token) + 280)
            value = text[left:right].replace("\n", " ").replace("\r", " ")
            if _printable(value) and value not in found:
                found.append(value)
            start = pos + len(token)
            if len(found) >= 80:
                return found
    return found


def test_austria_official_catalogue_bundle_routes_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    page = session.get(ROOT, timeout=45, allow_redirects=True)
    scripts = _scripts(page.text, page.url)
    official_host = urlparse(ROOT).hostname
    bundle_urls = [
        url for url in scripts
        if urlparse(url).hostname == official_host and urlparse(url).path.lower().endswith((".js", ".mjs"))
    ][:3]

    evidence = {
        "page": {
            "status": page.status_code,
            "final_url": page.url,
            "scripts": scripts,
        },
        "bundles": [],
    }
    for url in bundle_urls:
        response = session.get(url, timeout=45)
        text = response.text
        evidence["bundles"].append({
            "url": url,
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "bytes": len(response.content),
            "http_urls": _http_urls(text),
            "quoted_candidates": _quoted_candidates(text),
            "contexts": _contexts(text),
            "tail": text[-500:],
        })

    raise AssertionError(
        "AT_KERNDATEN_BUNDLE_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000]
    )
