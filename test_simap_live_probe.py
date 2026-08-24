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
    if depth >= 6:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _shape(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1)] if value else []
    return type(value).__name__


def _selected_scalars(value, path="", output=None):
    output = [] if output is None else output
    if len(output) >= 120:
        return output
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _selected_scalars(child, child_path, output)
            if len(output) >= 120:
                break
    elif isinstance(value, list):
        for index, child in enumerate(value[:3]):
            _selected_scalars(child, f"{path}[{index}]", output)
            if len(output) >= 120:
                break
    else:
        key = path.rsplit(".", 1)[-1].lower()
        if any(token in key for token in (
            "deadline", "date", "type", "status", "cpv", "bkp", "cpc",
            "lot", "publication", "project", "process", "corrected",
        )):
            output.append((path, value))
    return output


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
    response.raise_for_status()
    return response.json()


def test_simap_official_spec_and_public_contract_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    spec = session.get(SPEC_URL, timeout=45)
    spec.raise_for_status()
    text = spec.text
    assert "openapi:" in text[:5000].lower()
    block = _path_block(text, SEARCH_PATH)
    assert block, f"official OpenAPI spec does not declare {SEARCH_PATH}"
    parameter_names = sorted(set(re.findall(r"\bname:\s*([^\s#]+)", block)))
    for required in (
        "lastItem", "newestPublicationFrom", "newestPublicationUntil",
        "newestPubTypes", "projectSubTypes",
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
    assert isinstance(payload, dict)
    projects = payload.get("projects")
    pagination = payload.get("pagination")
    assert isinstance(projects, list) and projects
    assert isinstance(pagination, dict)
    first = projects[0]
    assert isinstance(first, dict)

    project_id = str(first.get("id") or "").strip()
    publication_id = str(first.get("publicationId") or "").strip()
    assert project_id and publication_id
    assert first.get("projectSubType") == "construction"
    assert first.get("pubType") == "tender"

    detail = _get(session, f"/publications/v1/project/{project_id}/publication-details/{publication_id}")
    header = _get(session, f"/publications/v2/project/{project_id}/project-header")
    history = _get(session, f"/publications/v1/publication/{publication_id}/past-publications")

    last_item = pagination.get("lastItem")
    page2_summary = None
    if last_item:
        page2 = _get(session, SEARCH_PATH, params=params + [("lastItem", str(last_item))])
        projects2 = page2.get("projects") if isinstance(page2, dict) else None
        assert isinstance(projects2, list)
        ids1 = {str(row.get("id")) for row in projects if isinstance(row, dict)}
        ids2 = {str(row.get("id")) for row in projects2 if isinstance(row, dict)}
        assert not (ids1 & ids2)
        page2_summary = {
            "count": len(projects2),
            "pagination": page2.get("pagination"),
            "overlap": sorted(ids1 & ids2),
        }

    evidence = {
        "spec_bytes": len(spec.content),
        "search_parameters": parameter_names,
        "search_shape": _shape(payload),
        "first_project": first,
        "detail_shape": _shape(detail),
        "detail_selected": _selected_scalars(detail),
        "header_shape": _shape(header),
        "header_selected": _selected_scalars(header),
        "history_shape": _shape(history),
        "history_selected": _selected_scalars(history),
        "pagination": pagination,
        "page2": page2_summary,
        "cookies": sorted(session.cookies.keys()),
    }
    # Deliberate one-run forensic stop so pytest includes the live shape in CI
    # logs. This assertion is temporary and MUST be removed after inspection.
    raise AssertionError("SIMAP_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:30000])
