"""TEMPORARY TenderNed public TNS pagination contract probe.

Delete before merge. No credentials are used. This is the final bounded live
probe before permanent offline implementation and intentionally fails only after
printing the pagination evidence.
"""
from __future__ import annotations

import json

import requests

BASE = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"


def _page(session, *, page, size):
    response = session.get(
        BASE,
        params={"page": page, "size": size},
        headers={"Accept": "application/json", "User-Agent": "ObraSignal TenderNed forensic probe/3.0"},
        timeout=45,
    )
    payload = response.json() if response.status_code == 200 else None
    content = payload.get("content") if isinstance(payload, dict) else None
    rows = [r for r in content if isinstance(r, dict)] if isinstance(content, list) else []
    ids = [int(r["publicatieId"]) for r in rows if str(r.get("publicatieId") or "").isdigit()]
    meta = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "content":
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                meta[key] = value
            elif isinstance(value, dict):
                meta[key] = value
    return response, payload, rows, ids, meta


def test_tenderned_public_tns_pagination_live():
    session = requests.Session()
    evidence = {}

    r0, _, rows0, ids0, meta0 = _page(session, page=0, size=10)
    r1, _, rows1, ids1, meta1 = _page(session, page=1, size=10)
    r100, _, rows100, ids100, meta100 = _page(session, page=0, size=100)
    r250, _, rows250, ids250, meta250 = _page(session, page=0, size=250)

    evidence["page0_size10"] = {"status": r0.status_code, "count": len(rows0), "ids": ids0, "meta": meta0}
    evidence["page1_size10"] = {"status": r1.status_code, "count": len(rows1), "ids": ids1, "meta": meta1}
    evidence["page0_size100"] = {
        "status": r100.status_code,
        "count": len(rows100),
        "first_ids": ids100[:10],
        "last_ids": ids100[-10:],
        "meta": meta100,
    }
    evidence["page0_size250"] = {
        "status": r250.status_code,
        "count": len(rows250),
        "first_ids": ids250[:10],
        "last_ids": ids250[-10:],
        "meta": meta250,
    }
    evidence["page01_overlap"] = sorted(set(ids0) & set(ids1))
    evidence["page0_desc"] = all(a > b for a, b in zip(ids0, ids0[1:]))
    evidence["page1_desc"] = all(a > b for a, b in zip(ids1, ids1[1:]))
    evidence["size100_desc"] = all(a > b for a, b in zip(ids100, ids100[1:]))
    evidence["size250_desc"] = all(a > b for a, b in zip(ids250, ids250[1:]))

    assert r0.status_code == 200 and r1.status_code == 200
    assert ids0 and ids1 and not (set(ids0) & set(ids1))
    assert all(a > b for a, b in zip(ids0, ids0[1:]))
    assert all(a > b for a, b in zip(ids1, ids1[1:]))
    raise AssertionError("TENDERNED_PAGINATION_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:90000])
