"""TEMPORARY Lithuania CVP IS semantic/snapshot probe.

Delete before merge. The apiKey is the public shared key published verbatim by
Lithuania's Public Procurement Office in its official API instructions.
The probe intentionally fails after bounded evidence is printed.
"""
from datetime import datetime, timezone
import json

import requests

ENDPOINT = "https://viesiejipirkimai.lt/epps-integration/api/cft-details-export"
PUBLIC_API_KEY = "acec29bd-687c-4609-b211-c01b6cf51b55"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "apiKey": PUBLIC_API_KEY,
    "User-Agent": "ObraSignal Lithuania VPT forensic probe/3.0",
}
TARGET_OPEN = 9333230
TARGET_CONSULTATION = 9327248
TARGET_AWARDED = 8009747


def _post(session, page_size, page_num):
    response = session.post(
        ENDPOINT,
        headers=HEADERS,
        json={"pageSize": page_size, "pageNum": page_num},
        timeout=60,
    )
    payload = response.json() if response.status_code == 200 else None
    rows = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
    return response, rows


def _clean(row):
    if not isinstance(row, dict):
        return None
    # Preserve the publisher's complete schema but cap unexpectedly large nested
    # values so the CI log remains bounded.
    out = {}
    for key, value in sorted(row.items()):
        if isinstance(value, str) and len(value) > 1500:
            out[key] = value[:1500] + "…"
        elif isinstance(value, (list, dict)):
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
            out[key] = value if len(encoded) <= 3000 else encoded[:3000] + "…"
        else:
            out[key] = value
    return out


def test_lithuania_semantic_snapshot_contract_live():
    session = requests.Session()
    evidence = {"at": datetime.now(timezone.utc).isoformat()}

    # 2,000-row pages reduce the ~74k corpus to ~38 requests for a complete
    # snapshot. Validate adjacent tail pages and an empty page beyond the tail.
    r37, rows37 = _post(session, 2000, 37)
    r38, rows38 = _post(session, 2000, 38)
    r39, rows39 = _post(session, 2000, 39)
    evidence["snapshot"] = {
        "p37_status": r37.status_code,
        "p37_count": len(rows37),
        "p38_status": r38.status_code,
        "p38_count": len(rows38),
        "p39_status": r39.status_code,
        "p39_count": len(rows39),
        "p37_p38_overlap": len({r.get("id") for r in rows37} & {r.get("id") for r in rows38}),
    }

    combined = rows37 + rows38
    open_hit = next((row for row in combined if row.get("id") == TARGET_OPEN), None)
    consultation_hit = next((row for row in combined if row.get("id") == TARGET_CONSULTATION), None)
    evidence["open_bid_submission"] = _clean(open_hit)
    evidence["proposal_submission"] = _clean(consultation_hit)

    # Historical mutable lifecycle sample, using the already-proven 100-row page.
    rh, historical = _post(session, 100, 640)
    awarded = next((row for row in historical if row.get("id") == TARGET_AWARDED), None)
    evidence["awarded_historical"] = {
        "status": rh.status_code,
        "row": _clean(awarded),
    }

    assert r37.status_code == r38.status_code == r39.status_code == 200
    assert open_hit is not None
    assert consultation_hit is not None
    assert awarded is not None
    raise AssertionError("LT_VPT_SEMANTIC_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:90000])
