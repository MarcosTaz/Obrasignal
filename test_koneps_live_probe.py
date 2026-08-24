"""TEMPORARY KONEPS/G2B access probe. Delete before merge.

Tests only official public surfaces. It intentionally fails after printing bounded
evidence so production architecture can be selected from observed behavior.
"""
from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urljoin, urlparse

import requests

REPORT_URL = "https://data.g2b.go.kr/link/AISC001_01/?reptNm=UI-ADOFAA-010R"
API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def _text(response, limit=30000):
    ctype = (response.headers.get("content-type") or "").lower()
    if any(token in ctype for token in ("text", "json", "xml", "html", "javascript")):
        return response.text[:limit]
    return ""


def _extract_html_contract(text):
    actions = re.findall(r"<form[^>]+action=[\"']([^\"']+)", text, flags=re.I)
    hrefs = re.findall(r"href=[\"']([^\"']+)", text, flags=re.I)
    srcs = re.findall(r"src=[\"']([^\"']+)", text, flags=re.I)
    interesting = []
    for value in hrefs + srcs:
        decoded = unescape(value)
        low = decoded.lower()
        if any(token in low for token in ("csv", "excel", "xlsx", "download", "export", "aisc", "report", "rept")):
            if decoded not in interesting:
                interesting.append(decoded)
    tokens = sorted(set(re.findall(r"[A-Za-z0-9_=&%./?${}:~-]{0,80}(?:download|export|excel|csv|reptNm|UI-ADOFAA-010R)[A-Za-z0-9_=&%./?${}:~-]{0,140}", text, flags=re.I)))
    return {
        "form_actions": actions[:20],
        "hrefs": hrefs[:80],
        "srcs": srcs[:40],
        "interesting_refs": interesting[:80],
        "tokens": tokens[:120],
    }


def test_koneps_official_surfaces_live():
    session = requests.Session()
    session.headers.update({
        "User-Agent": CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
    })
    evidence = {}

    report = session.get(REPORT_URL, timeout=60, allow_redirects=True)
    report_text = _text(report)
    contract = _extract_html_contract(report_text)
    evidence["g2b_report"] = {
        "status": report.status_code,
        "url": report.url,
        "history": [{"status": item.status_code, "url": item.url, "location": item.headers.get("location")} for item in report.history],
        "content_type": report.headers.get("content-type"),
        "length": len(report.content),
        "prefix": report_text[:9000],
        "html_contract": contract,
        "cookies": sorted(session.cookies.keys()),
    }

    # Inspect only a bounded number of scripts explicitly referenced by the
    # supported public page, looking for its own documented/public export calls.
    scripts = []
    for src in contract.get("srcs", []):
        url = urljoin(report.url, unescape(src))
        if urlparse(url).hostname not in {"data.g2b.go.kr", "www.g2b.go.kr"}:
            continue
        if url in [entry["url"] for entry in scripts]:
            continue
        try:
            response = session.get(url, timeout=45, allow_redirects=True)
        except requests.RequestException as exc:
            scripts.append({"url": url, "error": type(exc).__name__})
            continue
        text = _text(response, 40000)
        scripts.append({
            "url": url,
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "length": len(response.content),
            "tokens": _extract_html_contract(text).get("tokens", []),
        })
        if len(scripts) >= 8:
            break
    evidence["referenced_scripts"] = scripts

    # Confirm the credential boundary of the documented real-time OpenAPI.
    api = session.get(
        API_URL,
        params={
            "pageNo": 1,
            "numOfRows": 1,
            "type": "json",
            "bidNtceBgnDt": "202608230000",
            "bidNtceEndDt": "202608242359",
        },
        headers={"Accept": "application/json", "User-Agent": CHROME_UA},
        timeout=60,
        allow_redirects=True,
    )
    evidence["openapi_without_key"] = {
        "status": api.status_code,
        "url": api.url,
        "content_type": api.headers.get("content-type"),
        "length": len(api.content),
        "prefix": _text(api, 5000),
    }

    raise AssertionError("KONEPS_CHROME_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000])
