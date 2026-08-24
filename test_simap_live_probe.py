"""TEMPORARY live forensic probe for Swiss SIMAP lot/lifecycle semantics.

This file is intentionally network-dependent and MUST be deleted once the
upstream contract has been evidenced. Permanent CI must remain offline.
"""
from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo

import requests

BASE = "https://www.simap.ch/api"
SEARCH = "/publications/v2/project/project-search"
ZURICH = ZoneInfo("Europe/Zurich")
HEADERS = {"Accept": "application/json", "User-Agent": "ObraSignal temporary forensic validator/1.0"}


def _get_json(session, path, params=None):
    response = session.get(f"{BASE}{path}", params=params, timeout=45)
    response.raise_for_status()
    return response.json()


def _interesting(value, path="", out=None):
    out = [] if out is None else out
    if len(out) >= 180:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            _interesting(child, f"{path}.{key}" if path else str(key), out)
            if len(out) >= 180:
                break
    elif isinstance(value, list):
        for index, child in enumerate(value[:5]):
            _interesting(child, f"{path}[{index}]", out)
            if len(out) >= 180:
                break
    else:
        leaf = path.rsplit(".", 1)[-1].lower()
        if any(token in leaf for token in (
            "deadline", "date", "type", "status", "cpv", "bkp", "cpc",
            "ebkp", "npk", "oag", "lot", "publication", "project", "process",
            "correct", "reference", "id",
        )):
            out.append((path, value))
    return out


def _base_window(days=365):
    today = datetime.now(ZURICH).date()
    return [
        ("newestPublicationFrom", (today - timedelta(days=days)).isoformat()),
        ("newestPublicationUntil", today.isoformat()),
        ("projectSubTypes", "construction"),
    ]


def _find_with_predicate(session, *, pub_type="tender", predicate=lambda _row: True, max_pages=20):
    params = _base_window() + [("newestPubTypes", pub_type)]
    token = None
    for page_number in range(1, max_pages + 1):
        page_params = params + ([("lastItem", token)] if token else [])
        payload = _get_json(session, SEARCH, page_params)
        projects = payload.get("projects") if isinstance(payload, dict) else None
        assert isinstance(projects, list)
        for row in projects:
            if isinstance(row, dict) and predicate(row):
                return page_number, row, payload.get("pagination")
        pagination = payload.get("pagination") or {}
        next_token = pagination.get("lastItem")
        if not next_token or next_token == token:
            break
        token = str(next_token)
    return None, None, None


def _hydrate_evidence(session, row):
    project_id = str(row.get("id") or "")
    publication_id = str(row.get("publicationId") or "")
    assert project_id and publication_id
    header = _get_json(session, f"/publications/v2/project/{project_id}/project-header")
    detail = _get_json(session, f"/publications/v1/project/{project_id}/publication-details/{publication_id}")
    history = None
    history_error = None
    response = session.get(
        f"{BASE}/publications/v1/publication/{publication_id}/past-publications", timeout=45
    )
    if response.status_code < 400:
        history = response.json()
    else:
        history_error = {"status": response.status_code, "body": response.text[:500]}
    return {
        "search": row,
        "header": _interesting(header),
        "detail": _interesting(detail),
        "history": _interesting(history) if history is not None else None,
        "history_error": history_error,
    }


def test_simap_lot_lifecycle_and_human_url_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    lot_page, lot_row, lot_pagination = _find_with_predicate(
        session, predicate=lambda row: bool(row.get("lots"))
    )
    assert lot_row, "No construction tender with lots found within bounded probe"
    lot_evidence = _hydrate_evidence(session, lot_row)
    project_id = str(lot_row.get("id") or "")

    human_url = f"https://www.simap.ch/en/project-detail/{project_id}"
    human = session.get(human_url, timeout=45, allow_redirects=True)
    human.raise_for_status()
    assert "text/html" in (human.headers.get("content-type") or "").lower()
    assert "/project-detail/" in human.url

    corrected_page, corrected_row, _ = _find_with_predicate(
        session, predicate=lambda row: row.get("corrected") is True
    )
    corrected = _hydrate_evidence(session, corrected_row) if corrected_row else None

    negatives = {}
    for pub_type in ("revocation", "abandonment"):
        _page, row, _pagination = _find_with_predicate(
            session, pub_type=pub_type, predicate=lambda _row: True, max_pages=2
        )
        negatives[pub_type] = _hydrate_evidence(session, row) if row else None

    assert corrected or any(negatives.values()), "No corrected/revoked/abandoned construction example found"

    evidence = {
        "lot_page": lot_page,
        "lot_pagination": lot_pagination,
        "lot": lot_evidence,
        "corrected_page": corrected_page,
        "corrected": corrected,
        "negative_latest": negatives,
        "human": {
            "requested": human_url,
            "final": human.url,
            "status": human.status_code,
            "content_type": human.headers.get("content-type"),
            "bytes": len(human.content),
        },
        "cookies": sorted(session.cookies.keys()),
    }
    raise AssertionError("SIMAP_TARGET_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000])
