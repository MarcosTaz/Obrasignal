"""TEMPORARY German Public Procurement Data Service OpenData probe.

Only official public surfaces are tested. The probe intentionally fails after
printing bounded evidence. Delete before any production merge.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import requests

BASE = "https://oeffentlichevergabe.de"
SWAGGER = f"{BASE}/documentation/swagger-ui/opendata/index.html"
EXPORTS = f"{BASE}/api/notice-exports"
UA = "ObraSignal Germany DOE forensic probe/1.0"


def _summary(response, limit=120000):
    raw = response.content[:limit]
    ctype = response.headers.get("content-type") or ""
    text = raw.decode("utf-8", errors="replace") if any(x in ctype.lower() for x in ("text", "json", "xml", "javascript", "html", "yaml")) else ""
    return {
        "status": response.status_code,
        "url": response.url,
        "content_type": ctype,
        "content_length": response.headers.get("content-length"),
        "content_disposition": response.headers.get("content-disposition"),
        "bytes": len(raw),
        "prefix": text[:20000],
    }


def _candidate_docs(html):
    values = []
    for pattern in (
        r"configUrl\s*[:=]\s*[\"']([^\"']+)",
        r"url\s*[:=]\s*[\"']([^\"']+(?:api-docs|openapi)[^\"']*)",
        r"[\"']([^\"']*(?:v3/api-docs|openapi[^\"']*\.(?:json|yaml|yml)))[\"']",
        r"src=[\"']([^\"']+\.js[^\"']*)[\"']",
    ):
        for value in re.findall(pattern, html, flags=re.I):
            absolute = urljoin(SWAGGER, value)
            if absolute not in values:
                values.append(absolute)
    return values[:40]


def test_germany_doe_opendata_contract_live():
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    evidence = {}

    swagger = session.get(SWAGGER, timeout=45)
    swagger_text = swagger.text[:200000] if swagger.status_code == 200 else ""
    evidence["swagger"] = _summary(swagger)
    candidates = _candidate_docs(swagger_text)
    evidence["swagger_candidates"] = candidates

    docs = {}
    for candidate in candidates[:12]:
        try:
            response = session.get(candidate, timeout=30)
            info = _summary(response, 180000)
            if response.status_code == 200 or "api-docs" in candidate or "openapi" in candidate:
                docs[candidate] = info
        except requests.RequestException as exc:
            docs[candidate] = {"error": type(exc).__name__, "message": str(exc)[:300]}
    evidence["candidate_responses"] = docs

    # Probe the official export endpoint conservatively. pubDay/pubMonth are
    # documented by the official Open Data policy; response details reveal the
    # exact format/validation contract without inventing production behavior.
    attempts = {}
    for name, params, accept in (
        ("no_params", {}, "*/*"),
        ("pub_day", {"pubDay": "2026-08-24"}, "*/*"),
        ("pub_day_json", {"pubDay": "2026-08-24"}, "application/json"),
        ("pub_month", {"pubMonth": "2026-08"}, "*/*"),
    ):
        try:
            response = session.get(EXPORTS, params=params, headers={"Accept": accept}, timeout=60, stream=True)
            data = b""
            try:
                for chunk in response.iter_content(65536):
                    data += chunk
                    if len(data) >= 262144:
                        break
            finally:
                response.close()
            ctype = response.headers.get("content-type") or ""
            text = data.decode("utf-8", errors="replace") if any(x in ctype.lower() for x in ("text", "json", "xml", "html", "yaml")) else ""
            attempts[name] = {
                "status": response.status_code,
                "url": response.url,
                "content_type": ctype,
                "content_length": response.headers.get("content-length"),
                "content_disposition": response.headers.get("content-disposition"),
                "sample_bytes": len(data),
                "magic_hex": data[:16].hex(),
                "prefix": text[:15000],
            }
        except requests.RequestException as exc:
            attempts[name] = {"error": type(exc).__name__, "message": str(exc)[:500]}
    evidence["exports"] = attempts

    raise AssertionError("GERMANY_DOE_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
