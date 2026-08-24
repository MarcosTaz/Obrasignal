"""TEMPORARY KONEPS/G2B access probe. Delete before merge.

Tests only official public surfaces. It intentionally fails after printing bounded
evidence so production architecture can be selected from observed behavior.
"""
from __future__ import annotations

import json
import re

import requests

REPORT_URL = "https://data.g2b.go.kr/link/AISC001_01/?reptNm=UI-ADOFAA-010R"
SCREEN_URL = "https://data.g2b.go.kr/ui/ai/ais/aisc/SprnReptDtlT.xml"
API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def _text(response, limit=60000):
    ctype = (response.headers.get("content-type") or "").lower()
    if any(token in ctype for token in ("text", "json", "xml", "html", "javascript")):
        return response.text[:limit]
    return ""


def _screen_contract(text):
    submissions = []
    for match in re.finditer(r"<[^>]*(?:submission|action)[^>]*>", text, flags=re.I):
        tag = match.group(0)
        if tag not in submissions:
            submissions.append(tag[:1200])
    actions = re.findall(r"(?:action|ref|target|url|src)\s*=\s*[\"']([^\"']+)[\"']", text, flags=re.I)
    tokens = []
    for pattern in (
        r"[^\s\"'<>]{0,120}(?:download|export|excel|xlsx|csv|rept|report)[^\s\"'<>]{0,180}",
        r"/[A-Za-z0-9_./-]+\.(?:do|wq|json|xml|csv|xlsx)",
    ):
        for value in re.findall(pattern, text, flags=re.I):
            if value not in tokens:
                tokens.append(value)
    return {"submissions": submissions[:80], "actions": actions[:160], "tokens": tokens[:200]}


def test_koneps_official_surfaces_live():
    session = requests.Session()
    session.headers.update({
        "User-Agent": CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
    })
    evidence = {}

    report = session.get(REPORT_URL, timeout=60, allow_redirects=True)
    evidence["g2b_report"] = {
        "status": report.status_code,
        "url": report.url,
        "content_type": report.headers.get("content-type"),
        "length": len(report.content),
        "anonymous_marker": "const usrInfo = null" in _text(report),
        "screen_marker": "SprnReptDtlT.xml" in _text(report),
    }

    screen = session.get(SCREEN_URL, timeout=60, allow_redirects=True)
    screen_text = _text(screen)
    evidence["report_screen"] = {
        "status": screen.status_code,
        "url": screen.url,
        "content_type": screen.headers.get("content-type"),
        "length": len(screen.content),
        "prefix": screen_text[:15000],
        "contract": _screen_contract(screen_text),
    }

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
    )
    evidence["openapi_without_key"] = {
        "status": api.status_code,
        "content_type": api.headers.get("content-type"),
        "prefix": _text(api, 3000),
    }

    raise AssertionError("KONEPS_SCREEN_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:140000])
