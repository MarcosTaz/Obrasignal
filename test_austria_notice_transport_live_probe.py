"""TEMPORARY Austria probe: Z1 XSD flags + Hubexo duplicate semantics.
Delete before merge. Intentionally fails after bounded evidence is emitted.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import requests

HEADERS = {"User-Agent": "ObraSignal temporary Austria forensic probe/1.0"}
Z1_XSD = "https://ausschreibungen.usp.gv.at/schema/latest/kd-8-1-z1.xsd"
HUBEXO_KDQ = "https://www.ausschreibung.at/OpenData/kdq?id=87BA5ED1"
HUBEXO_ITEMS = ("899FC4871C63FACD", "701AB593054DF14D", "C3661D2BA33721CA", "28A1BA69A2BF04CC")
MAX_BYTES = 8 * 1024 * 1024
XS_NS = "http://www.w3.org/2001/XMLSchema"


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    if elem is None:
        return ""
    return " ".join(" ".join(elem.itertext()).split())


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
        item_id = str(elem.attrib.get("id") or "").strip()
        url = ""
        for child in elem:
            if _local(child.tag).lower() == "url":
                url = _text(child).strip()
        if item_id and url:
            out[item_id] = {"id": item_id, "lastmod": str(elem.attrib.get("lastmod") or ""), "url": url}
    return out


def _xsd_structure(blob):
    root = ET.fromstring(blob)
    result = {"target_namespace": root.attrib.get("targetNamespace"), "complex_types": {}, "global_elements": []}
    for ctype in root.findall(f"{{{XS_NS}}}complexType"):
        name = ctype.attrib.get("name") or ""
        rows = []
        for elem in ctype.iter(f"{{{XS_NS}}}element"):
            rows.append({
                "name": elem.attrib.get("name"),
                "ref": elem.attrib.get("ref"),
                "type": elem.attrib.get("type"),
                "min": elem.attrib.get("minOccurs"),
                "max": elem.attrib.get("maxOccurs"),
            })
        docs = [" ".join((doc.text or "").split()) for doc in ctype.iter(f"{{{XS_NS}}}documentation") if (doc.text or "").strip()]
        result["complex_types"][name] = {"elements": rows, "docs": docs}
    for elem in root.findall(f"{{{XS_NS}}}element"):
        result["global_elements"].append({"name": elem.attrib.get("name"), "ref": elem.attrib.get("ref"), "type": elem.attrib.get("type")})
    return result


def _walk(elem, path=""):
    name = _local(elem.tag)
    here = f"{path}/{name}"
    rows = []
    text = " ".join((elem.text or "").split())
    if text or elem.attrib or not list(elem):
        rows.append({"path": here, "text": text[:500], "attrs": {str(k): str(v)[:300] for k, v in elem.attrib.items()}})
    for child in elem:
        rows.extend(_walk(child, here))
    return rows


def _semantic_pairs(root):
    pairs = []
    for row in _walk(root):
        path = row["path"]
        if path.endswith("/URL_DOCUMENT"):
            continue
        if path.endswith("/PHONE") or path.endswith("/E_MAIL"):
            continue
        value = row["text"]
        attrs = row["attrs"]
        if not value and not attrs:
            continue
        pairs.append((path, value, tuple(sorted(attrs.items()))))
    return pairs


def _digest(pairs):
    payload = json.dumps(pairs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _interesting(rows):
    tokens = ("TITLE", "REFERENCE", "NATIONAL", "LOT", "OBJECT", "CPV", "TYPE_CONTRACT", "RECEIPT", "NOTICE", "PROCEDURE", "P")
    out = []
    for row in rows:
        upper = row["path"].upper()
        if any(token in upper for token in tokens):
            out.append(row)
        if len(out) >= 160:
            break
    return out


def test_austria_z1_flags_and_hubexo_duplicates_live():
    session = requests.Session()
    evidence = {}

    xsd_blob = _get(session, Z1_XSD)
    evidence["z1_xsd"] = _xsd_structure(xsd_blob)

    kdq_items = _kdq_items(_get(session, HUBEXO_KDQ))
    notices = []
    for item_id in HUBEXO_ITEMS:
        item = kdq_items[item_id]
        root = ET.fromstring(_get(session, item["url"]))
        rows = _walk(root)
        semantic = _semantic_pairs(root)
        notices.append({
            "item": item,
            "root": _local(root.tag),
            "semantic_sha256_without_url_contact": _digest(semantic),
            "semantic_pair_count": len(semantic),
            "interesting_tree": _interesting(rows),
        })
    evidence["hubexo"] = {
        "notices": notices,
        "all_semantic_hashes_equal": len({row["semantic_sha256_without_url_contact"] for row in notices}) == 1,
    }

    raise AssertionError("AT_Z1_FLAGS_HUBEXO_DUPLICATES_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000])
