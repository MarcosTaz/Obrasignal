"""TEMPORARY KONEPS/G2B access probe. Delete before merge.

Tests only official public surfaces. It intentionally fails after printing bounded
evidence so production architecture can be selected from observed behavior.
"""
from __future__ import annotations

import json
import re
from html import unescape

import requests

REPORT_URL = "https://data.g2b.go.kr/link/AISC001_01/?reptNm=UI-ADOFAA-010R"
API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"


def _text(response, limit=16000):
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
    tokens = sorted(set(re.findall(r"[A-Za-z0-9_./?-]{0,60}(?:download|export|excel|csv|reptNm|UI-ADOFAA-010R)[A-Za-z0-9_=&./?-]{0,100}", text, flags=re.I)))
    return {"form_actions": actions[:20], "interesting_refs": interesting[:60], "tokens": tokens[:100]}


def test_koneps_official_surfaces_live():
    session = requests.Session()
    session.headers.update({"User-Agent": "ObraSignal KONEPS forensic probe/1.0", "Accept": "*/*"})
    evidence = {}

    report = session.get(REPORT_URL, timeout=60, allow_redirects=True)
    report_text = _text(report)
    evidence["g2b_report"] = {
        "status": report.status_code,
        "url": report.url,
        "history": [{"status": item.status_code, "url": item.url, "location": item.headers.get("location")} for item in report.history],
        "content_type": report.headers.get("content-type"),
        "length": len(report.content),
        "prefix": report_text[:5000],
        "html_contract": _extract_html_contract(report_text),
        "cookies": sorted(session.cookies.keys()),
    }

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

    raise AssertionError("KONEPS_ACCESS_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:90000])
