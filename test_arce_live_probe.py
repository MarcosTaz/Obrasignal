"""Temporary forensic probe for Uruguay ARCE record release references; remove after inspection."""
import re
import xml.etree.ElementTree as ET

import requests

ARCE_RSS = "https://www.comprasestatales.gub.uy/ocds/rss"
ARCE_RECORD_ROOT = "https://www.comprasestatales.gub.uy/ocds/record"
HEADERS = {
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
    "Accept": "application/rss+xml, application/xml;q=0.9, application/json;q=0.9, */*;q=0.1",
}


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(item, name):
    for child in item:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _purchase_id(title):
    match = re.search(r"(?:^|,)\s*id_compra\s*:\s*([^,\s]+)", title or "", flags=re.I)
    return match.group(1) if match else ""


def _summary(value):
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(value.keys())}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "first_type": type(value[0]).__name__ if value else None}
    text = str(value)
    return text[:300]


def test_arce_record_release_reference_shape_live():
    response = requests.get(ARCE_RSS, headers=HEADERS, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    channel = next(node for node in root if _local(node.tag) == "channel")
    items = [node for node in channel if _local(node.tag) == "item"]
    item = next(item for item in items if "tender" in _text(item, "category").lower())
    purchase_id = _purchase_id(_text(item, "title"))
    assert purchase_id

    detail = requests.get(f"{ARCE_RECORD_ROOT}/{purchase_id}", headers=HEADERS, timeout=30)
    detail.raise_for_status()
    package = detail.json()
    records = package.get("records") if isinstance(package, dict) else None
    assert isinstance(records, list) and records
    record = records[0]
    releases = [release for release in (record.get("releases") or []) if isinstance(release, dict)]
    assert releases

    samples = []
    for release in releases[:3] + releases[-3:]:
        samples.append({
            "keys": sorted(release.keys()),
            "values": {key: _summary(value) for key, value in release.items()},
        })
    raise AssertionError({
        "purchase_id": purchase_id,
        "ocid": record.get("ocid"),
        "record_keys": sorted(record.keys()),
        "release_count": len(releases),
        "samples": samples,
    })
