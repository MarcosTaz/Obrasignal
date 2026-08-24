"""TEMPORARY live probe for Austria actionable Works and lifecycle identity.

Delete before merge. Intentionally fails after bounded evidence is emitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


HEADERS = {
    "Accept": "application/xml,text/xml,application/octet-stream,*/*;q=0.5",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
MAX_KDQ_BYTES = 8 * 1024 * 1024
MAX_NOTICE_BYTES = 4 * 1024 * 1024
MAX_SCAN = 100
MAX_ACTIONABLE_HITS = 4
HUBEXO_KDQ = "https://www.ausschreibung.at/OpenData/kdq?id=87BA5ED1"
MVG_KDQ = "https://opendata.mvg.at/mvg_kerndaten.xml"


def _local(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _ns(tag: str) -> str:
    text = str(tag)
    return text[1:].split("}", 1)[0] if text.startswith("{") and "}" in text else ""


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return " ".join(elem.text.split())


def _first(root: ET.Element, name: str) -> ET.Element | None:
    for elem in root.iter():
        if _local(elem.tag) == name:
            return elem
    return None


def _attr(root: ET.Element, name: str, attr: str) -> str:
    elem = _first(root, name)
    return "" if elem is None else str(elem.attrib.get(attr) or "").strip()


def _bounded_get(session: requests.Session, url: str, max_bytes: int) -> tuple[bytes, dict]:
    response = session.get(url, timeout=60, stream=True, allow_redirects=True)
    response.raise_for_status()
    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(131072):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise AssertionError(f"resource exceeds {max_bytes} bytes: {url}")
            chunks.append(chunk)
    finally:
        response.close()
    return b"".join(chunks), {
        "status": response.status_code,
        "final_url": response.url,
        "host": urlparse(response.url).hostname,
        "content_type": response.headers.get("content-type"),
        "received": total,
    }


def _kdq_items(root: ET.Element) -> list[dict]:
    if _local(root.tag).lower() != "kdq":
        raise AssertionError(f"unexpected KDQ root: {root.tag}")
    rows = []
    for elem in root.iter():
        if _local(elem.tag).lower() != "item":
            continue
        url = ""
        for child in elem:
            if _local(child.tag).lower() == "url":
                url = _text(child).strip()
                break
        if url:
            rows.append({
                "id": str(elem.attrib.get("id") or "").strip(),
                "lastmod": str(elem.attrib.get("lastmod") or "").strip(),
                "url": url,
            })
    rows.sort(key=lambda row: row.get("lastmod") or "", reverse=True)
    return rows


def _deadline(root: ET.Element) -> str:
    return _text(_first(root, "DATETIME_RECEIPT_TENDERS"))


def _reference(root: ET.Element) -> str:
    return _text(_first(root, "REFERENCE_NUMBER"))


def _cpv(root: ET.Element) -> str:
    elem = _first(root, "CPV_CODE")
    return "" if elem is None else str(elem.attrib.get("CODE") or "").strip()


def _buyer_national_id(root: ET.Element) -> str:
    return _text(_first(root, "NATIONALID"))


def _summary(root: ET.Element, item: dict, transport: dict) -> dict:
    return {
        "item": item,
        "root": _local(root.tag),
        "root_ns": _ns(root.tag),
        "reference_number": _reference(root),
        "buyer_national_id": _buyer_national_id(root),
        "contract_type": _attr(root, "TYPE_CONTRACT", "CTYPE"),
        "cpv_main": _cpv(root),
        "deadline": _deadline(root),
        "date_first_publication": _text(_first(root, "DATE_FIRST_PUBLICATION")),
        "datetime_last_change": _text(_first(root, "DATETIME_LAST_CHANGE")),
        "date_conclusion_contract": _text(_first(root, "DATE_CONCLUSION_CONTRACT")),
        "url_document": _text(_first(root, "URL_DOCUMENT")),
        "transport": transport,
    }


def _is_future(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc) > datetime.now(timezone.utc)


def _fetch_notice(session: requests.Session, item: dict) -> tuple[ET.Element, dict]:
    blob, transport = _bounded_get(session, item["url"], MAX_NOTICE_BYTES)
    return ET.fromstring(blob), transport


def _actionable_works(session: requests.Session, items: list[dict]) -> dict:
    hits = []
    roots_seen: dict[str, int] = {}
    scanned = 0
    errors = []
    for item in items[:MAX_SCAN]:
        scanned += 1
        try:
            root, transport = _fetch_notice(session, item)
        except Exception as exc:
            errors.append({"item": item, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            continue
        root_name = _local(root.tag)
        roots_seen[root_name] = roots_seen.get(root_name, 0) + 1
        if root_name != "KD_8_1_Z2":
            continue
        if _attr(root, "TYPE_CONTRACT", "CTYPE") != "WORKS":
            continue
        deadline = _deadline(root)
        if not _is_future(deadline):
            continue
        hits.append(_summary(root, item, transport))
        if len(hits) >= MAX_ACTIONABLE_HITS:
            break
    return {"scanned": scanned, "roots_seen": roots_seen, "hits": hits, "errors": errors[:8]}


def _mvg_lifecycle_pair(session: requests.Session, items: list[dict]) -> dict:
    by_id = {row["id"]: row for row in items if row.get("id")}
    candidates = []
    for award_item in items:
        item_id = award_item.get("id") or ""
        if not item_id.endswith("_Award"):
            continue
        base = item_id[:-6]
        tender_item = by_id.get(base)
        if not tender_item:
            continue
        candidates.append((tender_item, award_item))
        if len(candidates) >= 8:
            break

    evidence = {"candidate_pairs": len(candidates), "pairs": []}
    for tender_item, award_item in candidates:
        try:
            tender_root, tender_transport = _fetch_notice(session, tender_item)
            award_root, award_transport = _fetch_notice(session, award_item)
            tender = _summary(tender_root, tender_item, tender_transport)
            award = _summary(award_root, award_item, award_transport)
            evidence["pairs"].append({
                "same_reference": bool(tender["reference_number"] and tender["reference_number"] == award["reference_number"]),
                "same_buyer_national_id": bool(tender["buyer_national_id"] and tender["buyer_national_id"] == award["buyer_national_id"]),
                "tender": tender,
                "award": award,
            })
            if evidence["pairs"][-1]["same_reference"]:
                break
        except Exception as exc:
            evidence["pairs"].append({
                "tender_item": tender_item,
                "award_item": award_item,
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            })
    return evidence


def test_austria_actionable_and_identity_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {"at": datetime.now(timezone.utc).isoformat()}

    hubexo_blob, hubexo_transport = _bounded_get(session, HUBEXO_KDQ, MAX_KDQ_BYTES)
    hubexo_items = _kdq_items(ET.fromstring(hubexo_blob))
    evidence["hubexo"] = {
        "kdq_transport": hubexo_transport,
        "item_count": len(hubexo_items),
        "actionable_works": _actionable_works(session, hubexo_items),
    }

    mvg_blob, mvg_transport = _bounded_get(session, MVG_KDQ, MAX_KDQ_BYTES)
    mvg_items = _kdq_items(ET.fromstring(mvg_blob))
    evidence["mvg"] = {
        "kdq_transport": mvg_transport,
        "item_count": len(mvg_items),
        "lifecycle_identity": _mvg_lifecycle_pair(session, mvg_items),
    }

    raise AssertionError(
        "AT_KERNDATEN_ACTIONABLE_IDENTITY_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000]
    )
