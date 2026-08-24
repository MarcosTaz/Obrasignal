"""TEMPORARY live forensic probe for the official Swiss simap.ch API.

This file MUST be deleted once the upstream contract has been evidenced. It is
intentionally network-dependent and must never remain in permanent CI.
"""
from datetime import datetime, timedelta
import json
import re
from zoneinfo import ZoneInfo

import requests


BASE = "https://www.simap.ch/api"
SPEC_URL = f"{BASE}/specifications/simap.yaml"
SEARCH_PATH = "/publications/v2/project/project-search"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal temporary forensic validator/1.0",
}
ZURICH = ZoneInfo("Europe/Zurich")


def _shape(value, depth=0):
    if depth >= 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _shape(v, depth + 1) for k, v in list(value.items())[:30]}
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


def _get(session, path, *, params=None):
    response = session.get(f"{BASE}{path}", params=params, timeout=45)
    print(
        "SIMAP_GET",
        response.status_code,
        response.url,
        response.headers.get("content-type"),
        response.text[:1000] if response.status_code >= 400 else "",
    )
    response.raise_for_status()
    return response.json()


def test_simap_official_spec_and_public_contract_live():
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
    for required in (
        "lastItem",
        "newestPublicationFrom",
        "newestPublicationUntil",
        "newestPubTypes",
        "projectSubTypes",
    ):
        assert required in parameter_names

    today = datetime.now(ZURICH).date()
    start = today - timedelta(days=30)
    params = [
        ("newestPublicationFrom", start.isoformat()),
        ("newestPublicationUntil", today.isoformat()),
        ("projectSubTypes", "construction"),
        ("newestPubTypes", "tender"),
    ]
    payload = _get(session, SEARCH_PATH, params=params)
    print("SIMAP_SEARCH_SHAPE", json.dumps(_shape(payload), ensure_ascii=False, sort_keys=True)[:8000])
    assert isinstance(payload, dict)
    projects = payload.get("projects")
    pagination = payload.get("pagination")
    assert isinstance(projects, list) and projects, "30-day construction+tender search returned no projects"
    assert isinstance(pagination, dict)
    first = projects[0]
    assert isinstance(first, dict)
    print("SIMAP_FIRST_PROJECT", json.dumps(first, ensure_ascii=False, sort_keys=True)[:12000])

    project_id = str(first.get("id") or "").strip()
    publication_id = str(first.get("publicationId") or "").strip()
    assert project_id and publication_id
    assert first.get("projectSubType") == "construction"
    assert first.get("pubType") == "tender"

    detail_path = f"/publications/v1/project/{project_id}/publication-details/{publication_id}"
    detail = _get(session, detail_path)
    print("SIMAP_DETAIL_SHAPE", json.dumps(_shape(detail), ensure_ascii=False, sort_keys=True)[:12000])
    assert isinstance(detail, dict)

    header_path = f"/publications/v2/project/{project_id}/project-header"
    header = _get(session, header_path)
    print("SIMAP_HEADER_SHAPE", json.dumps(_shape(header), ensure_ascii=False, sort_keys=True)[:10000])
    assert isinstance(header, dict)

    history_path = f"/publications/v1/publication/{publication_id}/past-publications"
    history = _get(session, history_path)
    print("SIMAP_HISTORY_SHAPE", json.dumps(_shape(history), ensure_ascii=False, sort_keys=True)[:10000])
    assert isinstance(history, (dict, list))

    last_item = pagination.get("lastItem")
    print("SIMAP_PAGINATION", json.dumps(pagination, ensure_ascii=False, sort_keys=True))
    if last_item:
        page2 = _get(session, SEARCH_PATH, params=params + [("lastItem", str(last_item))])
        projects2 = page2.get("projects") if isinstance(page2, dict) else None
        assert isinstance(projects2, list)
        ids1 = {str(row.get("id")) for row in projects if isinstance(row, dict)}
        ids2 = {str(row.get("id")) for row in projects2 if isinstance(row, dict)}
        print("SIMAP_PAGE2", len(projects2), "overlap", sorted(ids1 & ids2)[:10])
        assert not (ids1 & ids2), "opaque pagination repeated project ids across adjacent pages"

    print("SIMAP_COOKIES", sorted(session.cookies.keys()))
