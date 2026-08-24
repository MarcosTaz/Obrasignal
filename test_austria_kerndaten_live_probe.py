"""TEMPORARY live discovery probe for Austria BVergG Kerndaten.

Previous probes proved that data.gv.at is a Piveau SPA and that its catalogue
service uses a runtime ``api.baseUrl``. This probe discovers only the runtime
configuration bootstrap and follows same-host config paths literally exposed by
the official HTML/bundle. Remove before merge.
"""
from urllib.parse import urljoin, urlparse
import json
import re

import requests

ROOT = "https://www.data.gv.at/"
HEADERS = {
    "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.8",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
TOKENS = (
    "fetchjsonconfig", "fetchjson(", "glueconfig", "config.json", ".json",
    "window.location", "api.baseurl", "baseurl", "huburl", "$env", "env:",
)


def _scripts(html_text, base_url):
    found = []
    for match in re.finditer(r"<script([^>]*)>(.*?)</script>", html_text or "", re.I | re.S):
        attrs, body = match.groups()
        src = re.search(r"\bsrc=[\"']([^\"']+)[\"']", attrs, re.I)
        if src:
            found.append({"src": urljoin(base_url, src.group(1)), "inline": None})
        elif body.strip():
            found.append({"src": None, "inline": body.strip()[:4000]})
    return found


def _contexts(text, token, *, radius=450, limit=20):
    lowered = (text or "").lower()
    needle = token.lower()
    found = []
    start = 0
    while True:
        pos = lowered.find(needle, start)
        if pos < 0:
            break
        value = text[max(0, pos - radius):min(len(text), pos + len(token) + radius)]
        value = value.replace("\n", " ").replace("\r", " ")
        if value not in found:
            found.append(value)
        start = pos + len(needle)
        if len(found) >= limit:
            break
    return found


def _quoted_config_literals(text):
    found = []
    for match in re.finditer(r"[\"']([^\"'\\\n\r]{1,300})[\"']", text or ""):
        value = match.group(1).strip()
        low = value.lower()
        if not value:
            continue
        if not ("config" in low or "env" in low or low.endswith(".json") or "settings" in low):
            continue
        # Keep route/file-like literals only; discard prose and library messages.
        if len(value) > 180 or " " in value and not low.startswith(("http://", "https://")):
            continue
        if value not in found:
            found.append(value)
        if len(found) >= 80:
            break
    return found


def _same_host_config_urls(literals, base_url):
    host = urlparse(base_url).hostname
    urls = []
    for literal in literals:
        if not literal:
            continue
        low = literal.lower()
        if not ("config" in low or "env" in low or low.endswith(".json") or "settings" in low):
            continue
        candidate = urljoin(base_url, literal)
        parsed = urlparse(candidate)
        if parsed.scheme not in ("http", "https") or parsed.hostname != host:
            continue
        if candidate not in urls:
            urls.append(candidate)
    return urls[:12]


def _response_summary(response):
    payload = None
    try:
        payload = response.json()
    except Exception:
        pass
    return {
        "status": response.status_code,
        "final_url": response.url,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
        "json": payload if isinstance(payload, (dict, list)) else None,
        "body_prefix": None if payload is not None else response.text[:2500],
    }


def test_austria_official_runtime_config_discovery_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    page = session.get(ROOT, timeout=45, allow_redirects=True)
    scripts = _scripts(page.text, page.url)
    bundle_urls = [entry["src"] for entry in scripts if entry.get("src")]

    evidence = {
        "page": {
            **_response_summary(page),
            "scripts": scripts,
            "config_contexts": {
                token: _contexts(page.text, token, radius=350, limit=8)
                for token in TOKENS if token.lower() in page.text.lower()
            },
        },
        "bundles": [],
        "discovered_config_requests": [],
    }

    literals = []
    for url in bundle_urls[:3]:
        response = session.get(url, timeout=45)
        text = response.text
        bundle_literals = _quoted_config_literals(text)
        for value in bundle_literals:
            if value not in literals:
                literals.append(value)
        evidence["bundles"].append({
            "url": url,
            "status": response.status_code,
            "bytes": len(response.content),
            "config_literals": bundle_literals,
            "contexts": {
                token: _contexts(text, token, radius=500, limit=12)
                for token in TOKENS if token.lower() in text.lower()
            },
        })

    for entry in scripts:
        inline = entry.get("inline")
        if inline:
            for value in _quoted_config_literals(inline):
                if value not in literals:
                    literals.append(value)

    for url in _same_host_config_urls(literals, page.url):
        try:
            response = session.get(url, timeout=45, allow_redirects=True)
            evidence["discovered_config_requests"].append({"requested": url, **_response_summary(response)})
        except requests.RequestException as exc:
            evidence["discovered_config_requests"].append({"requested": url, "error": type(exc).__name__})

    raise AssertionError(
        "AT_KERNDATEN_RUNTIME_CONFIG_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000]
    )
