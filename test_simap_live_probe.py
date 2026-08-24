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


def _find_project_with_lots(session):
    params = _base_window() + [("newestPubTypes", "tender")]
    token = None
    for page_number in range(1, 21):
        page_params = params + ([("lastItem", token)] if token else [])
        payload = _get_json(session, SEARCH, page_params)
        projects = payload.get("projects") if isinstance(payload, dict) else None
        assert isinstance(projects, list)
        for row in projects:
            if isinstance(row, dict) and row.get("lots"):
                return page_number, row, payload.get("pagination")
        pagination = payload.get("pagination") or {}
        next_token = pagination.get("lastItem")
        if not next_token or next_token == token:
            break
        token = str(next_token)
    return None, None, None


def _find_negative_latest(session):
    findings = {}
    for pub_type in ("correction", "revocation", "abandonment"):
        payload = _get_json(session, SEARCH, _base_window() + [("newestPubTypes", pub_type)])
        projects = payload.get("projects") if isinstance(payload, dict) else None
        assert isinstance(projects, list)
        if not projects:
            findings[pub_type] = None
            continue
        row = projects[0]
        project_id = str(row.get("id") or "")
        publication_id = str(row.get("publicationId") or "")
        assert project_id and publication_id
        header = _get_json(session, f"/publications/v2/project/{project_id}/project-header")
        detail = _get_json(session, f"/publications/v1/project/{project_id}/publication-details/{publication_id}")
        history = _get_json(session, f"/publications/v1/publication/{publication_id}/past-publications")
        findings[pub_type] = {
            "search": row,
            "header": _interesting(header),
            "detail": _interesting(detail),
            "history": _interesting(history),
        }
    return findings


def test_simap_lot_lifecycle_and_human_url_live():
    session = requests.Session()
    session.headers.update(HEADERS)

    lot_page, lot_row, lot_pagination = _find_project_with_lots(session)
    assert lot_row, "No construction tender with lots found within bounded 20-page / 365-day probe"
    project_id = str(lot_row.get("id") or "")
    publication_id = str(lot_row.get("publicationId") or "")
    assert project_id and publication_id

    lot_header = _get_json(session, f"/publications/v2/project/{project_id}/project-header")
    lot_detail = _get_json(session, f"/publications/v1/project/{project_id}/publication-details/{publication_id}")

    human_url = f"https://www.simap.ch/en/project-detail/{project_id}"
    human = session.get(human_url, timeout=45, allow_redirects=True)
    human.raise_for_status()
    assert "text/html" in (human.headers.get("content-type") or "").lower()
    assert "/project-detail/" in human.url

    negatives = _find_negative_latest(session)
    assert any(negatives.values()), "No correction/revocation/abandonment construction examples found"

    evidence = {
        "lot_page": lot_page,
        "lot_search": lot_row,
        "lot_pagination": lot_pagination,
        "lot_header": _interesting(lot_header),
        "lot_detail": _interesting(lot_detail),
        "human": {
            "requested": human_url,
            "final": human.url,
            "status": human.status_code,
            "content_type": human.headers.get("content-type"),
            "bytes": len(human.content),
        },
        "negative_latest": negatives,
        "cookies": sorted(session.cookies.keys()),
    }
    # One-run forensic stop: print bounded evidence into failure logs, then this
    # entire live probe will be removed and replaced with deterministic tests.
    raise AssertionError("SIMAP_TARGET_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:45000])
