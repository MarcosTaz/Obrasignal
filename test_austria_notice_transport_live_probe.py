"""TEMPORARY Austria probe: inspect Z1 and Hubexo identity/duplication fields.
Delete before merge. Intentionally fails after bounded evidence is emitted.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import requests

HEADERS = {"User-Agent": "ObraSignal temporary Austria forensic probe/1.0"}
DATASET_ID = "fde58043-87ff-44b0-b6b0-3d089adfba4c"
Z1_ITEM_ID = "FN_227986z_BVergG-VIII-1-Z1_240329"
HUBEXO_KDQ = "https://www.ausschreibung.at/OpenData/kdq?id=87BA5ED1"
HUBEXO_ITEMS = ("899FC4871C63FACD", "701AB593054DF14D", "C3661D2BA33721CA", "28A1BA69A2BF04CC")
MAX_BYTES = 8 * 1024 * 1024


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    return "" if elem is None or elem.text is None else " ".join(str(elem.text).split())


def _get(session, url, accept="application/xml,text/xml,*/*"):
    r = session.get(url, headers={**HEADERS, "Accept": accept}, timeout=60, stream=True, allow_redirects=True)
    r.raise_for_status()
    out = bytearray()
    try:
        for chunk in r.iter_content(131072):
            if chunk:
                out.extend(chunk)
            if len(out) > MAX_BYTES:
                raise AssertionError(f"too large: {url}")
    finally:
        r.close()
    return bytes(out)


def _kdq_items(blob):
    root = ET.fromstring(blob)
    assert _local(root.tag).lower() == "kdq"
    out = {}
    for elem in root.iter():
        if _local(elem.tag).lower() != "item":
            continue
        url = ""
        for child in elem:
            if _local(child.tag).lower() == "url":
                url = _text(child).strip()
        item_id = str(elem.attrib.get("id") or "").strip()
        if item_id and url:
            out[item_id] = {"id": item_id, "lastmod": str(elem.attrib.get("lastmod") or ""), "url": url}
    return out


def _leafs(root, limit=180):
    rows = []
    for elem in root.iter():
        if list(elem):
            continue
        text = _text(elem)
        attrs = {str(k): str(v)[:250] for k, v in elem.attrib.items()}
        if text or attrs:
            rows.append({"tag": _local(elem.tag), "text": text[:500], "attrs": attrs})
        if len(rows) >= limit:
            break
    return rows


def _summary(root):
    values = {}
    for elem in root.iter():
        name = _local(elem.tag)
        if name in {
            "TITLE", "REFERENCE_NUMBER", "NATIONALID", "CPV_CODE", "TYPE_CONTRACT",
            "DATETIME_RECEIPT_TENDERS", "DATETIME_RECEIPT_PARTICIPATION",
            "DATE_FIRST_PUBLICATION", "DATETIME_LAST_CHANGE", "URL_DOCUMENT",
            "SHORT_DESCR", "NOTICE_CALL_FOR_COMPETITION", "NOTICE_NUMBER_OJ",
        }:
            values.setdefault(name, []).append({"text": _text(elem)[:500], "attrs": dict(elem.attrib)})
    refish = []
    for elem in root.iter():
        name = _local(elem.tag)
        if any(token in name.upper() for token in ("REF", "NUMBER", "NATIONAL", "ID")):
            text = _text(elem)
            if text or elem.attrib:
                refish.append({"tag": name, "text": text[:500], "attrs": dict(elem.attrib)})
            if len(refish) >= 80:
                break
    return {"root": _local(root.tag), "values": values, "refish": refish, "leafs": _leafs(root)}


def _access_urls(payload):
    out = []
    for node in payload.get("@graph") or []:
        if not isinstance(node, dict):
            continue
        access = node.get("dcat:accessURL")
        candidates = access if isinstance(access, list) else [access]
        for value in candidates:
            if isinstance(value, dict):
                url = str(value.get("@id") or "").strip()
                if url and url not in out:
                    out.append(url)
    return out


def test_austria_z1_and_hubexo_identity_live():
    session = requests.Session()
    evidence = {"z1": {}, "hubexo": []}

    meta = session.get(
        f"https://www.data.gv.at/api/hub/repo/datasets/{DATASET_ID}",
        headers={**HEADERS, "Accept": "application/ld+json"}, timeout=60,
    )
    meta.raise_for_status()
    urls = _access_urls(meta.json())
    evidence["z1"]["dataset_access_urls"] = urls
    for kdq_url in urls:
        try:
            items = _kdq_items(_get(session, kdq_url))
        except Exception as exc:
            evidence["z1"].setdefault("kdq_errors", []).append(f"{kdq_url}: {type(exc).__name__}: {str(exc)[:400]}")
            continue
        if Z1_ITEM_ID not in items:
            continue
        item = items[Z1_ITEM_ID]
        root = ET.fromstring(_get(session, item["url"]))
        evidence["z1"].update({"kdq_url": kdq_url, "item": item, "notice": _summary(root)})
        break

    hubexo_items = _kdq_items(_get(session, HUBEXO_KDQ))
    for item_id in HUBEXO_ITEMS:
        item = hubexo_items[item_id]
        root = ET.fromstring(_get(session, item["url"]))
        evidence["hubexo"].append({"item": item, "notice": _summary(root)})

    raise AssertionError("AT_Z1_HUBEXO_IDENTITY_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000])
