"""TEMPORARY live probe for Austria KDQ -> notice XML semantics.

Delete before merge. Intentionally fails after emitting bounded forensic evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


HEADERS = {
    "Accept": "application/xml,text/xml,application/octet-stream,*/*;q=0.5",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
MAX_KDQ_BYTES = 8 * 1024 * 1024
MAX_NOTICE_BYTES = 8 * 1024 * 1024
MAX_ITEMS_PER_KDQ = 4
KDQS = {
    "hubexo": "https://www.ausschreibung.at/OpenData/kdq?id=87BA5ED1",
    "mvg": "https://opendata.mvg.at/mvg_kerndaten.xml",
    "social_insurance": "https://opendata.sozialversicherung.at/BVergG/kdq.xml",
}


def _local(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _ns(tag: str) -> str:
    text = str(tag)
    if text.startswith("{") and "}" in text:
        return text[1:].split("}", 1)[0]
    return ""


def _text(elem: ET.Element) -> str:
    if elem.text is None:
        return ""
    return " ".join(elem.text.split())


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
        "content_length": response.headers.get("content-length"),
        "received": total,
    }


def _parse_xml(blob: bytes) -> ET.Element:
    return ET.fromstring(blob)


def _kdq_items(root: ET.Element) -> list[dict]:
    if _local(root.tag).lower() != "kdq":
        raise AssertionError(f"unexpected KDQ root: {root.tag}")
    rows: list[dict] = []
    for elem in root.iter():
        if _local(elem.tag).lower() != "item":
            continue
        url = ""
        for child in elem:
            if _local(child.tag).lower() == "url":
                url = _text(child).strip()
                break
        if not url:
            continue
        rows.append({
            "id": str(elem.attrib.get("id") or "").strip(),
            "lastmod": str(elem.attrib.get("lastmod") or "").strip(),
            "url": url,
        })
    rows.sort(key=lambda row: row.get("lastmod") or "", reverse=True)
    return rows


def _looks_cpv(value: str) -> bool:
    compact = re.sub(r"[^0-9]", "", value)
    return len(compact) in (8, 9) and compact.startswith(("45", "44", "71"))


def _summarize_notice(root: ET.Element) -> dict:
    cpv_hits: list[dict] = []
    deadline_hits: list[dict] = []
    identity_hits: list[dict] = []
    lifecycle_hits: list[dict] = []
    type_hits: list[dict] = []
    eforms_markers: list[dict] = []
    leaf_sample: list[dict] = []
    all_namespaces: list[str] = []

    deadline_tokens = ("frist", "deadline", "submission", "angebot", "receipt", "enddate", "endtime")
    identity_tokens = ("id", "identifier", "uuid", "notice", "publication", "version", "reference")
    lifecycle_tokens = ("award", "zuschlag", "widerruf", "revocation", "cancel", "aufhebung", "status")
    type_tokens = ("type", "art", "contract", "auftrag", "procedure", "verfahren")

    for elem in root.iter():
        tag = _local(elem.tag)
        low_tag = tag.lower()
        ns = _ns(elem.tag)
        if ns and ns not in all_namespaces and len(all_namespaces) < 30:
            all_namespaces.append(ns)
        value = _text(elem)
        attrs = {str(k): str(v)[:250] for k, v in elem.attrib.items()}
        joined = " ".join([value, *attrs.values()]).strip()
        low_joined = joined.lower()
        row = {"tag": tag, "text": value[:350], "attrs": attrs}

        if joined and (_looks_cpv(joined) or "cpv" in low_tag or "cpv" in low_joined):
            if len(cpv_hits) < 40:
                cpv_hits.append(row)
        if joined and any(token in low_tag for token in deadline_tokens):
            if len(deadline_hits) < 40:
                deadline_hits.append(row)
        if joined and any(token in low_tag for token in identity_tokens):
            if len(identity_hits) < 40:
                identity_hits.append(row)
        if joined and (any(token in low_tag for token in lifecycle_tokens) or any(token in low_joined for token in ("award", "zuschlag", "widerruf", "revocation", "cancelled", "aufgehoben"))):
            if len(lifecycle_hits) < 40:
                lifecycle_hits.append(row)
        if joined and any(token in low_tag for token in type_tokens):
            if len(type_hits) < 40:
                type_hits.append(row)

        ns_low = ns.lower()
        if any(token in ns_low for token in ("oasis", "ubl", "eforms", "ted")):
            marker = {"tag": tag, "ns": ns[-220:]}
            if marker not in eforms_markers and len(eforms_markers) < 30:
                eforms_markers.append(marker)

        if value and len(leaf_sample) < 70 and not list(elem):
            leaf_sample.append(row)

    return {
        "root": _local(root.tag),
        "root_ns": _ns(root.tag),
        "namespaces": all_namespaces,
        "cpv_hits": cpv_hits,
        "deadline_hits": deadline_hits,
        "identity_hits": identity_hits,
        "lifecycle_hits": lifecycle_hits,
        "type_hits": type_hits,
        "eforms_markers": eforms_markers,
        "leaf_sample": leaf_sample,
    }


def test_austria_kdq_notice_transport_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {"at": datetime.now(timezone.utc).isoformat(), "publishers": {}}

    for name, kdq_url in KDQS.items():
        publisher = {"kdq_url": kdq_url}
        evidence["publishers"][name] = publisher
        try:
            kdq_blob, kdq_transport = _bounded_get(session, kdq_url, MAX_KDQ_BYTES)
            kdq_root = _parse_xml(kdq_blob)
            items = _kdq_items(kdq_root)
            publisher.update({
                "kdq_transport": kdq_transport,
                "kdq_root": _local(kdq_root.tag),
                "kdq_ns": _ns(kdq_root.tag),
                "item_count": len(items),
                "latest_items": items[:MAX_ITEMS_PER_KDQ],
                "notices": [],
            })
            for item in items[:MAX_ITEMS_PER_KDQ]:
                row = {"item": item}
                try:
                    blob, transport = _bounded_get(session, item["url"], MAX_NOTICE_BYTES)
                    root = _parse_xml(blob)
                    row["transport"] = transport
                    row["summary"] = _summarize_notice(root)
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {str(exc)[:700]}"
                publisher["notices"].append(row)
        except Exception as exc:
            publisher["error"] = f"{type(exc).__name__}: {str(exc)[:700]}"

    raise AssertionError(
        "AT_KERNDATEN_NOTICE_EVIDENCE "
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:120000]
    )
