"""TEMPORARY Austria probe: resolve Z1 competition flags exactly.
Delete before merge. Intentionally fails after bounded evidence is emitted.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import requests

HEADERS = {"User-Agent": "ObraSignal temporary Austria forensic probe/1.0"}
Z1_XSD = "https://ausschreibungen.usp.gv.at/schema/latest/kd-8-1-z1.xsd"
DATASET_ID = "fde58043-87ff-44b0-b6b0-3d089adfba4c"
Z1_ITEM_ID = "FN_227986z_BVergG-VIII-1-Z1_240329"
XS = "http://www.w3.org/2001/XMLSchema"
MAX_BYTES = 4 * 1024 * 1024


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    return "" if elem is None else " ".join(" ".join(elem.itertext()).split())


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


def _access_urls(payload):
    out = []
    for node in payload.get("@graph") or []:
        if not isinstance(node, dict):
            continue
        access = node.get("dcat:accessURL")
        vals = access if isinstance(access, list) else [access]
        for val in vals:
            if isinstance(val, dict):
                url = str(val.get("@id") or "").strip()
                if url and url not in out:
                    out.append(url)
    return out


def _kdq_items(blob):
    root = ET.fromstring(blob)
    out = {}
    for elem in root.iter():
        if _local(elem.tag) != "item":
            continue
        item_id = str(elem.attrib.get("id") or "").strip()
        url = ""
        for child in elem:
            if _local(child.tag) == "url":
                url = _text(child).strip()
        if item_id and url:
            out[item_id] = url
    return out


def _xsd_notice_contract(blob):
    root = ET.fromstring(blob)
    result = {}
    for ctype in root.findall(f"{{{XS}}}complexType"):
        if ctype.attrib.get("name") != "cd_notice_811":
            continue
        result["docs"] = [" ".join((d.text or "").split()) for d in ctype.iter(f"{{{XS}}}documentation") if (d.text or "").strip()]
        result["elements"] = [dict(e.attrib) for e in ctype.iter(f"{{{XS}}}element")]
        result["attributes"] = [dict(a.attrib) for a in ctype.iter(f"{{{XS}}}attribute")]
        result["attribute_groups"] = [dict(a.attrib) for a in ctype.iter(f"{{{XS}}}attributeGroup")]
        result["choices"] = [dict(c.attrib) for c in ctype.iter(f"{{{XS}}}choice")]
    root_elem = next((e for e in root.findall(f"{{{XS}}}element") if e.attrib.get("name") == "KD_8_1_Z1"), None)
    if root_elem is not None:
        result["root_descendant_elements"] = [dict(e.attrib) for e in root_elem.iter(f"{{{XS}}}element")]
    return result


def _live_notice_flags(root):
    rows = []
    for elem in root.iter():
        name = _local(elem.tag)
        upper = name.upper()
        if elem.attrib or any(token in upper for token in ("NOTICE", "INTEREST", "PRIOR", "SHORT", "CALL", "INVIT", "PROCUREMENT")):
            rows.append({"tag": name, "text": _text(elem)[:500], "attrs": {str(k): str(v) for k, v in elem.attrib.items()}})
    return rows[:160]


def test_austria_z1_competition_flags_live():
    session = requests.Session()
    xsd = _xsd_notice_contract(_get(session, Z1_XSD))

    meta = session.get(
        f"https://www.data.gv.at/api/hub/repo/datasets/{DATASET_ID}",
        headers={**HEADERS, "Accept": "application/ld+json"}, timeout=60,
    )
    meta.raise_for_status()
    live = {"access_urls": _access_urls(meta.json())}
    for kdq_url in live["access_urls"]:
        items = _kdq_items(_get(session, kdq_url))
        if Z1_ITEM_ID not in items:
            continue
        notice_url = items[Z1_ITEM_ID]
        root = ET.fromstring(_get(session, notice_url))
        live.update({"kdq_url": kdq_url, "notice_url": notice_url, "root": _local(root.tag), "flags": _live_notice_flags(root)})
        break

    raise AssertionError("AT_Z1_COMPETITION_FLAGS_EVIDENCE " + json.dumps({"xsd": xsd, "live": live}, ensure_ascii=False, sort_keys=True)[:80000])
