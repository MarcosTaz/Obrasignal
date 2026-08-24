"""Temporary forensic probe for official SERCOP bulk download routes; delete after contract freeze."""
import re
from urllib.parse import urljoin

import requests

PAGE = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos"
HEADERS = {
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
    "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.8",
}


def _snippets(text):
    needles = ("download", "descarg", "json", "bulk", "archivo", "openData", "datos-abiertos", "api/")
    found = []
    lower = text.lower()
    for needle in needles:
        start = 0
        while len(found) < 80:
            pos = lower.find(needle.lower(), start)
            if pos < 0:
                break
            left = max(0, pos - 180)
            right = min(len(text), pos + 350)
            snippet = re.sub(r"\s+", " ", text[left:right])
            if snippet not in found:
                found.append(snippet[:700])
            start = pos + len(needle)
    return found


def test_official_sercop_frontend_exposes_bulk_route_contract():
    page = requests.get(PAGE, headers=HEADERS, timeout=30)
    page.raise_for_status()
    scripts = []
    for src in re.findall(r'<script[^>]+src=["\']([^"\']+)', page.text, flags=re.I):
        url = urljoin(PAGE, src)
        if url not in scripts:
            scripts.append(url)

    diagnostics = {
        "page_status": page.status_code,
        "page_bytes": len(page.content),
        "page_snippets": _snippets(page.text)[:20],
        "script_count": len(scripts),
        "scripts": scripts[:30],
        "script_hits": [],
    }
    for url in scripts[:30]:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as exc:
            diagnostics["script_hits"].append({"url": url, "error": type(exc).__name__})
            continue
        if response.status_code != 200:
            continue
        hits = _snippets(response.text)
        if hits:
            diagnostics["script_hits"].append({
                "url": url,
                "status": response.status_code,
                "bytes": len(response.content),
                "snippets": hits[:20],
            })
    raise AssertionError(diagnostics)
