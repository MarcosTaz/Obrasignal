"""TEMPORARY TenderNed public RSS/TNS contract probe.

Delete before merge. No credentials are used. The feed URL is linked by
TenderNed itself as its public RSS surface.
This probe intentionally fails after bounded evidence is printed.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import requests

RSS_URL = "https://www.tenderned.nl/papi/tenderned-rs-tns/rss/laatste-publicatie.rss"
BASE = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"
MAX_IDS = 4


def _safe_text(response, limit=3000):
    ctype = (response.headers.get("content-type") or "").lower()
    if any(x in ctype for x in ("text", "json", "xml", "html")):
        return response.text[:limit]
    return ""


def _publication_id(entry):
    # Prefer an explicit link/id path segment. Do not assume Atom entry IDs are
    # numeric unless the publisher URL proves it.
    candidates = []
    for child in entry.iter():
        if child.tag.rsplit("}", 1)[-1] == "link":
            candidates.append(child.attrib.get("href") or "")
        if child.tag.rsplit("}", 1)[-1] in {"id", "guid"}:
            candidates.append(child.text or "")
    for value in candidates:
        match = re.search(r"/publicaties/(\d+)(?:/|$|[?#])", value)
        if match:
            return match.group(1)
    for value in candidates:
        match = re.search(r"(?:^|\D)(\d{4,})(?:\D|$)", value)
        if match:
            return match.group(1)
    return None


def _entry_summary(entry):
    out = {}
    for child in list(entry):
        name = child.tag.rsplit("}", 1)[-1]
        if name == "link":
            out.setdefault("links", []).append(dict(child.attrib))
        elif child.text and child.text.strip():
            out[name] = child.text.strip()[:1500]
    return out


def test_tenderned_public_rss_tns_contract_live():
    session = requests.Session()
    session.headers.update({"User-Agent": "ObraSignal TenderNed forensic probe/1.0", "Accept": "*/*"})
    evidence = {"feed": {}, "publications": []}

    feed = session.get(RSS_URL, timeout=45)
    evidence["feed"] = {
        "status": feed.status_code,
        "content_type": feed.headers.get("content-type"),
        "length": len(feed.content),
        "prefix": feed.text[:1500] if feed.status_code == 200 else _safe_text(feed),
    }
    assert feed.status_code == 200
    root = ET.fromstring(feed.content)
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "entry"]
    if not entries:
        entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "item"]
    evidence["feed"]["entry_count"] = len(entries)
    evidence["feed"]["entries"] = [_entry_summary(e) for e in entries[:8]]
    assert entries

    ids = []
    for entry in entries:
        pid = _publication_id(entry)
        if pid and pid not in ids:
            ids.append(pid)
        if len(ids) >= MAX_IDS:
            break
    evidence["feed"]["publication_ids"] = ids

    # Probe only bounded, obvious public-service shapes adjacent to the proven
    # public PDF route. We record exact status/content-type and never scrape a UI.
    for pid in ids:
        item = {"publication_id": pid, "routes": {}}
        for suffix in ("", "/public-xml", "/pdf"):
            url = f"{BASE}/{pid}{suffix}"
            response = session.get(url, timeout=45, allow_redirects=True)
            item["routes"][suffix or "/"] = {
                "status": response.status_code,
                "url": response.url,
                "content_type": response.headers.get("content-type"),
                "length": len(response.content),
                "prefix": _safe_text(response),
            }
        evidence["publications"].append(item)

    raise AssertionError("TENDERNED_PUBLIC_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:90000])
