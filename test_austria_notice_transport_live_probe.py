"""TEMPORARY Austria probe: resolve Z1 competition flags exactly.
Delete before merge. Intentionally fails after bounded evidence is emitted.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import requests

HEADERS = {"User-Agent": "ObraSignal temporary Austria forensic probe/1.0"}
Z1_XSD = "https://ausschreibungen.usp.gv.at/schema/latest/kd-8-1-z1.xsd"
Z1_NOTICE = "https://bekanntmachungen.vemap.com/FN_227986z_BVergG-VIII-1-Z1_240329.xml"
XS = "http://www.w3.org/2001/XMLSchema"
MAX_BYTES = 2 * 1024 * 1024


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    return "" if elem is None else " ".join(" ".join(elem.itertext()).split())


def _get(session, url):
    r = session.get(url, headers={**HEADERS, "Accept": "application/xml,text/xml,*/*"}, timeout=60, stream=True, allow_redirects=True)
    r.raise_for_status()
    out = bytearray()
    try:
        for chunk in r.iter_content(131072):
            if chunk:
                out.extend(chunk)
            if len(out) > MAX_BYTES:
                raise AssertionError(f"resource unexpectedly too large: {url}")
    finally:
        r.close()
    return bytes(out)


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
        result["simple_contents"] = [dict(s.attrib) for s in ctype.iter(f"{{{XS}}}simpleContent")]
        result["extensions"] = [dict(e.attrib) for e in ctype.iter(f"{{{XS}}}extension")]
    root_elem = next((e for e in root.findall(f"{{{XS}}}element") if e.attrib.get("name") == "KD_8_1_Z1"), None)
    if root_elem is not None:
        result["root_elements"] = [dict(e.attrib) for e in root_elem.iter(f"{{{XS}}}element")]
    return result


def _live_flags(root):
    rows = []
    for elem in root.iter():
        name = _local(elem.tag)
        upper = name.upper()
        if elem.attrib or any(token in upper for token in ("NOTICE", "INTEREST", "PRIOR", "SHORT", "CALL", "INVIT", "PROCUREMENT")):
            rows.append({
                "tag": name,
                "text": _text(elem)[:700],
                "attrs": {str(k): str(v) for k, v in elem.attrib.items()},
            })
    return rows[:180]


def test_austria_z1_competition_flags_live():
    session = requests.Session()
    xsd = _xsd_notice_contract(_get(session, Z1_XSD))
    root = ET.fromstring(_get(session, Z1_NOTICE))
    live = {"url": Z1_NOTICE, "root": _local(root.tag), "flags": _live_flags(root)}
    raise AssertionError("AT_Z1_COMPETITION_FLAGS_EVIDENCE " + json.dumps({"xsd": xsd, "live": live}, ensure_ascii=False, sort_keys=True)[:80000])
