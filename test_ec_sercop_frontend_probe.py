"""Temporary forensic probe for official SERCOP bulk download behavior; delete after contract freeze."""
import re

import requests

BASE = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA"
PAGE = f"{BASE}/datos-abiertos"
HEADERS = {
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def _context(text, needle, radius=1800):
    pos = text.find(needle)
    if pos < 0:
        return None
    return re.sub(r"\s+", " ", text[max(0, pos-radius): min(len(text), pos+len(needle)+radius)])[:4200]


def _peek(url):
    with requests.get(url, headers=HEADERS, timeout=60, stream=True, allow_redirects=True) as response:
        first = b""
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                first += chunk
            if len(first) >= 8192:
                break
        return {
            "requested_url": url,
            "status": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get("content-type"),
            "content_disposition": response.headers.get("content-disposition"),
            "content_length": response.headers.get("content-length"),
            "first_bytes_len": len(first),
            "first_hex": first[:32].hex(),
            "first_text": first[:600].decode("utf-8", errors="replace"),
        }


def test_official_sercop_bulk_variants_and_public_form_contract():
    page = requests.get(PAGE, headers=HEADERS, timeout=30)
    page.raise_for_status()

    method_match = re.search(r"const\s+methodList\s*=\s*(\[.*?\]);\s*const\s+basePath", page.text, flags=re.S)
    method_source = method_match.group(1) if method_match else None

    variants = {
        "august_all": f"{BASE}/download?type=json&year=2026&month=8&method=all",
        "july_all": f"{BASE}/download?type=json&year=2026&month=7&method=all",
        "annual_all": f"{BASE}/download?type=json&year=2026&month=0&method=all",
        "august_licitacion": f"{BASE}/download?type=json&year=2026&month=8&method=Licitaci%C3%B3n",
    }
    totals = {}
    for name, query in {
        "august_all": "year=2026&month=8&method=all",
        "july_all": "year=2026&month=7&method=all",
        "annual_all": "year=2026&month=0&method=all",
        "august_licitacion": "year=2026&month=8&method=Licitaci%C3%B3n",
    }.items():
        response = requests.get(f"{BASE}/get-totals?{query}", headers=HEADERS, timeout=30)
        totals[name] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "text": response.text[:800],
        }

    diagnostics = {
        "page_status": page.status_code,
        "method_source": method_source[:6000] if method_source else None,
        "download_path": _context(page.text, "return `${basePath}/download"),
        "totals": totals,
        "downloads": {name: _peek(url) for name, url in variants.items()},
    }
    raise AssertionError(diagnostics)
