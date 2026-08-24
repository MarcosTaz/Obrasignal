"""TEMPORARY live forensic probe for the official Swiss simap.ch API.

This file MUST be deleted once the upstream contract has been evidenced. It is
intentionally network-dependent and must never remain in permanent CI.
"""
import json
import re

import requests


BASE = "https://www.simap.ch/api"
SPEC_URL = f"{BASE}/specifications/simap.yaml"
SEARCH_PATH = "/publications/v2/project/project-search"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary forensic validator/1.0",
}


def _shape(value, depth=0):
    if depth >= 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _shape(v, depth + 1) for k, v in list(value.items())[:20]}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1)] if value else []
    return type(value).__name__


def _path_block(spec_text, path):
    marker = f"  {path}:"
    start = spec_text.find(marker)
    if start < 0:
        return ""
    rest = spec_text[start + len(marker):]
    match = re.search(r"\n  /[^\n]+:\s*\n", rest)
    return rest[: match.start()] if match else rest


def test_simap_official_spec_and_public_search_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    spec = session.get(SPEC_URL, timeout=45)
    print("SIMAP_SPEC", spec.status_code, spec.headers.get("content-type"), len(spec.content))
    spec.raise_for_status()
    text = spec.text
    assert "openapi:" in text[:5000].lower()
    block = _path_block(text, SEARCH_PATH)
    assert block, f"official OpenAPI spec does not declare {SEARCH_PATH}"
    parameter_names = sorted(set(re.findall(r"\bname:\s*([^\s#]+)", block)))
    print("SIMAP_SEARCH_PARAMETERS", json.dumps(parameter_names, ensure_ascii=False))

    response = session.get(
        f"{BASE}{SEARCH_PATH}",
        params={"lang": "en"},
        timeout=45,
    )
    print(
        "SIMAP_SEARCH",
        response.status_code,
        response.url,
        response.headers.get("content-type"),
        response.text[:500] if response.status_code >= 400 else "",
    )
    response.raise_for_status()
    payload = response.json()
    print("SIMAP_SEARCH_SHAPE", json.dumps(_shape(payload), ensure_ascii=False, sort_keys=True)[:5000])
    print("SIMAP_COOKIES", sorted(session.cookies.keys()))
    assert isinstance(payload, (dict, list))
