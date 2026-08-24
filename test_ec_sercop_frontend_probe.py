"""Temporary forensic probe for official SERCOP bulk download behavior; delete after contract freeze."""
import re

import requests

BASE = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA"
PAGE = f"{BASE}/datos-abiertos"
HEADERS = {
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def _context(text, needle, radius=1400):
    pos = text.find(needle)
    if pos < 0:
        return None
    return re.sub(r"\s+", " ", text[max(0, pos-radius): min(len(text), pos+len(needle)+radius)])[:3200]


def test_official_sercop_frontend_and_month_bulk_contract():
    page = requests.get(PAGE, headers=HEADERS, timeout=30)
    page.raise_for_status()

    inline = {
        "base_path": _context(page.text, "basePath"),
        "download_path": _context(page.text, "return `${basePath}/download"),
        "set_contracts": _context(page.text, "setContracts"),
        "method_list": _context(page.text, "methodList"),
        "axios_calls": re.findall(r"axios\.(?:get|post)\(([^\n;]{1,500})", page.text),
    }

    url = f"{BASE}/download?type=json&year=2026&month=8&method="
    with requests.get(url, headers=HEADERS, timeout=60, stream=True, allow_redirects=True) as response:
        first = b""
        try:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    first += chunk
                if len(first) >= 16384:
                    break
        finally:
            response.close()
        diagnostics = {
            "page_status": page.status_code,
            "inline": inline,
            "download": {
                "requested_url": url,
                "status": response.status_code,
                "final_url": response.url,
                "content_type": response.headers.get("content-type"),
                "content_disposition": response.headers.get("content-disposition"),
                "content_length": response.headers.get("content-length"),
                "first_bytes_len": len(first),
                "first_text": first[:1500].decode("utf-8", errors="replace"),
            },
        }
    raise AssertionError(diagnostics)
