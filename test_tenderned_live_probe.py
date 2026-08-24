"""TEMPORARY TenderNed public discovery/lifecycle probe.

Delete before merge. No credentials are used. The RSS URL is linked by
TenderNed itself. This probe intentionally fails after bounded evidence is
printed so permanent CI never depends on the live service.
"""
from __future__ import annotations

from collections import Counter
import json
import re
import xml.etree.ElementTree as ET

import requests

RSS_URL = "https://www.tenderned.nl/papi/tenderned-rs-tns/rss/laatste-publicatie.rss"
BASE = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"
KNOWN_RECTIFICATION = 423151
SCAN_BACK = 45
MAX_CALLS = 70


def _publication_id(entry):
    candidates = []
    for child in entry.iter():
        name = child.tag.rsplit("}", 1)[-1]
        if name == "link":
            candidates.append(child.attrib.get("href") or "")
        elif name in {"id", "guid"}:
            candidates.append(child.text or "")
    for value in candidates:
        match = re.search(r"/overzicht/(\d+)(?:/|$|[?#])", value)
        if match:
            return int(match.group(1))
    return None


def _compact(row):
    if not isinstance(row, dict):
        return None
    keys = (
        "publicatieId", "kenmerk", "aanbestedingNaam", "opdrachtgeverNaam",
        "publicatieDatum", "sluitingsDatum", "typePublicatie", "publicatieCode",
        "typeOpdrachtCode", "procedureCode", "cpvCodes", "nutsCodes",
        "afgerondeAanbesteding", "isVroegtijdigBeeindigd", "isGegund",
        "aanbestedingStatus", "aankondigingCode", "gerelateerdePublicaties",
    )
    return {k: row.get(k) for k in keys if row.get(k) not in (None, "", [], {})}


def test_tenderned_public_discovery_lifecycle_live():
    session = requests.Session()
    session.headers.update({"User-Agent": "ObraSignal TenderNed forensic probe/2.0", "Accept": "*/*"})
    calls = 0

    def get(url, **kwargs):
        nonlocal calls
        calls += 1
        assert calls <= MAX_CALLS
        return session.get(url, timeout=30, allow_redirects=True, **kwargs)

    evidence = {"feed": {}, "list_routes": {}, "id_scan": {}, "rectification": {}}

    feed = get(RSS_URL)
    assert feed.status_code == 200
    root = ET.fromstring(feed.content)
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "entry"]
    feed_ids = [pid for pid in (_publication_id(e) for e in entries) if pid is not None]
    evidence["feed"] = {
        "status": feed.status_code,
        "content_type": feed.headers.get("content-type"),
        "count": len(entries),
        "ids": feed_ids,
        "strictly_descending": all(a > b for a, b in zip(feed_ids, feed_ids[1:])),
        "max_id": max(feed_ids) if feed_ids else None,
        "min_id": min(feed_ids) if feed_ids else None,
    }
    assert feed_ids
    latest = max(feed_ids)

    # Check whether the public JSON resource also exposes an undocumented list
    # route. If not, production discovery must not depend on it.
    list_shapes = {
        "plain": BASE,
        "page_size": BASE + "?page=0&size=25",
        "offset_limit": BASE + "?offset=0&limit=25",
        "page_num": BASE + "?pageNum=1&pageSize=25",
    }
    for name, url in list_shapes.items():
        response = get(url)
        ctype = response.headers.get("content-type") or ""
        prefix = response.text[:1200] if any(x in ctype.lower() for x in ("json", "text", "html", "xml")) else ""
        evidence["list_routes"][name] = {
            "status": response.status_code,
            "content_type": ctype,
            "length": len(response.content),
            "prefix": prefix,
        }

    # Probe a bounded contiguous ID range below the latest feed publication.
    # We need to know whether gaps are stable 404s versus auth/transient errors.
    statuses = Counter()
    public_rows = []
    for pid in range(max(1, latest - SCAN_BACK), latest + 1):
        response = get(f"{BASE}/{pid}")
        statuses[str(response.status_code)] += 1
        if response.status_code == 200:
            payload = response.json()
            public_rows.append(_compact(payload))
        elif response.status_code not in {404}:
            public_rows.append({"publicatieId": pid, "unexpected_status": response.status_code, "prefix": response.text[:500]})
    public_ids = [int(row["publicatieId"]) for row in public_rows if isinstance(row, dict) and row.get("publicatieId")]
    evidence["id_scan"] = {
        "from": max(1, latest - SCAN_BACK),
        "through": latest,
        "statuses": dict(statuses),
        "public_ids": public_ids,
        "feed_ids_in_range": [pid for pid in feed_ids if pid >= latest - SCAN_BACK],
        "sample": public_rows[:12],
    }

    # A known 2026 rectification validates stable commercial identity and the
    # publisher's related-publication graph without parsing PDF content.
    rect = get(f"{BASE}/{KNOWN_RECTIFICATION}")
    assert rect.status_code == 200
    rect_row = rect.json()
    evidence["rectification"]["current"] = _compact(rect_row)
    related = rect_row.get("gerelateerdePublicaties") or []
    related_rows = []
    for rel in related[:5]:
        rel_id = rel.get("publicatieId") if isinstance(rel, dict) else None
        if not rel_id:
            continue
        response = get(f"{BASE}/{int(rel_id)}")
        related_rows.append({
            "requested": int(rel_id),
            "status": response.status_code,
            "row": _compact(response.json()) if response.status_code == 200 else None,
        })
    evidence["rectification"]["related"] = related_rows
    evidence["calls"] = calls

    raise AssertionError("TENDERNED_DISCOVERY_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:90000])
