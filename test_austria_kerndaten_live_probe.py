"""TEMPORARY live probe for Austria KDQ -> notice transport and XML families.

Delete before merge. This intentionally prints bounded evidence via failure.
"""
from datetime import datetime, timezone
import json
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


KDQ_URL = "https://www.ausschreibung.at/OpenData/kdq?id=87BA5ED1"
HEADERS = {
    "Accept": "application/xml,text/xml,*/*;q=0.5",
    "User-Agent": "ObraSignal temporary Austria Kerndaten forensic probe/1.0",
}
MAX_KDQ_BYTES = 20 * 1024 * 1024
MAX_NOTICE_BYTES = 4 * 1024 * 1024
MAX_NOTICE_FETCHES = 16


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _namespace(tag):
    text = str(tag)
    return text[1:].split("}", 1)[0] if text.startswith("{") and "}" in text else ""


def _text(elem):
    return "" if elem is None or elem.text is None else " ".join(elem.text.split())


def _bounded_get(session, url, max_bytes):
    response = session.get(url, headers=HEADERS, timeout=90, stream=True, allow_redirects=True)
    response.raise_for_status()
    length = int(response.headers.get("content-length") or 0)
    if length and length > max_bytes:
        response.close()
        raise AssertionError(f"resource too large: {length} > {max_bytes}: {url}")
    chunks = []
    total = 0
    try:
        for chunk in response.iter_content(131072):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise AssertionError(f"stream exceeded limit {max_bytes}: {url}")
            chunks.append(chunk)
    finally:
        response.close()
    return b"".join(chunks), {
        "status": response.status_code,
        "final_url": response.url,
        "content_type": response.headers.get("content-type"),
        "content_length": length,
        "received": total,
    }


def _leaf_rows(root, limit=250):
    rows = []
    for elem in root.iter():
        if list(elem):
            continue
        value = _text(elem)
        if not value and not elem.attrib:
            continue
        rows.append({
            "tag": _local(elem.tag),
            "ns": _namespace(elem.tag)[-120:],
            "text": value[:500],
            "attrs": {str(k): str(v)[:300] for k, v in elem.attrib.items()},
        })
        if len(rows) >= limit:
            break
    return rows


def _all_urls(root):
    out = []
    seen = set()
    for elem in root.iter():
        candidates = [_text(elem), *[str(v) for v in elem.attrib.values()]]
        for value in candidates:
            value = value.strip()
            if not value.startswith(("http://", "https://")):
                continue
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
    return out


def _interesting_notice(root):
    rows = []
    construction_hits = []
    deadline_hits = []
    identity_hits = []
    eforms_markers = []
    for elem in root.iter():
        tag = _local(elem.tag)
        value = _text(elem)
        low_tag = tag.lower()
        low = value.lower()
        if value and (
            value.startswith("45")
            or "bauauftrag" in low
            or "bauleistung" in low
            or "works" == low
        ):
            construction_hits.append({"tag": tag, "text": value[:300], "attrs": dict(elem.attrib)})
        if value and any(token in low_tag for token in ("frist", "deadline", "submission", "angebots", "enddate", "endtime")):
            deadline_hits.append({"tag": tag, "text": value[:300], "attrs": dict(elem.attrib)})
        if value and any(token in low_tag for token in ("id", "identifier", "uuid", "version", "date", "zeit", "time")):
            if len(identity_hits) < 35:
                identity_hits.append({"tag": tag, "text": value[:300], "attrs": dict(elem.attrib)})
        ns = _namespace(elem.tag).lower()
        if "oasis" in ns or "ubl" in ns or "eforms" in ns or "ted" in ns:
            marker = {"tag": tag, "ns": ns[-180:]}
            if marker not in eforms_markers and len(eforms_markers) < 20:
                eforms_markers.append(marker)
        if len(rows) < 80 and value:
            rows.append({"tag": tag, "text": value[:300], "attrs": dict(elem.attrib)})
    return {
        "root": _local(root.tag),
        "root_ns": _namespace(root.tag),
        "construction_hits": construction_hits[:30],
        "deadline_hits": deadline_hits[:30],
        "identity_hits": identity_hits,
        "eforms_markers": eforms_markers,
        "leaf_sample": rows,
    }


def test_austria_kdq_and_notice_family_live():
    session = requests.Session()
    session.headers.update(HEADERS)
    evidence = {"at": datetime.now(timezone.utc).isoformat(), "kdq_url": KDQ_URL}

    payload, meta = _bounded_get(session, KDQ_URL, MAX_KDQ_BYTES)
    evidence["kdq_http"] = meta
    root = ET.fromstring(payload)
    evidence["kdq_root"] = {"tag": _local(root.tag), "ns": _namespace(root.tag), "attrs": dict(root.attrib)}
    evidence["kdq_leaf_sample"] = _leaf_rows(root)
    urls = _all_urls(root)
    evidence["kdq_url_count"] = len(urls)
    evidence["kdq_urls_sample"] = urls[:30]

    # Prefer URLs that look like actual XML notices over documentation/schema links.
    notice_urls = []
    for url in reversed(urls):
        host = (urlparse(url).hostname or "").lower()
        low = url.lower()
        if host.endswith("ausschreibung.at") and "kdq" not in low:
            notice_urls.append(url)
        if len(notice_urls) >= MAX_NOTICE_FETCHES:
            break
    if not notice_urls:
        notice_urls = list(reversed(urls[-MAX_NOTICE_FETCHES:]))

    evidence["notices"] = []
    for url in notice_urls[:MAX_NOTICE_FETCHES]:
        row = {"url": url}
        try:
            body, http = _bounded_get(session, url, MAX_NOTICE_BYTES)
            row["http"] = http
            notice = ET.fromstring(body)
            row.update(_interesting_notice(notice))
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        evidence["notices"].append(row)

    raise AssertionError("AT_KERNDATEN_KDQ_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:70000])
