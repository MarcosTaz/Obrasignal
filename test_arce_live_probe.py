"""Temporary forensic probe for Uruguay ARCE RSS -> OCDS record hydration; remove after inspection."""
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


def test_arce_tender_record_hydration_live():
    response = requests.get(ARCE_RSS, headers=HEADERS, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    channel = next(node for node in root if _local(node.tag) == "channel")
    items = [node for node in channel if _local(node.tag) == "item"]
    tender_items = [item for item in items if "tender" in _text(item, "category").lower()]
    assert tender_items, {"count": len(items), "categories": sorted({_text(item, 'category') for item in items})}

    item = tender_items[0]
    purchase_id = _purchase_id(_text(item, "title"))
    assert purchase_id, _text(item, "title")

    detail = requests.get(f"{ARCE_RECORD_ROOT}/{purchase_id}", headers=HEADERS, timeout=30)
    detail.raise_for_status()
    package = detail.json()
    assert isinstance(package, dict), type(package)
    records = package.get("records")
    assert isinstance(records, list) and records, package.keys()
    record = records[0]
    compiled = record.get("compiledRelease") if isinstance(record, dict) else None
    releases = record.get("releases") if isinstance(record, dict) else None
    latest = None
    if isinstance(releases, list) and releases:
        latest = max((release for release in releases if isinstance(release, dict)), key=lambda release: str(release.get("date") or ""), default=None)
    chosen = compiled if isinstance(compiled, dict) else latest
    assert isinstance(chosen, dict), sorted(record.keys())
    tender = chosen.get("tender") if isinstance(chosen.get("tender"), dict) else {}
    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    value = tender.get("value") if isinstance(tender.get("value"), dict) else {}

    diagnostics = {
        "rss_category": _text(item, "category"),
        "rss_title": _text(item, "title"),
        "purchase_id": purchase_id,
        "package_keys": sorted(package.keys()),
        "record_keys": sorted(record.keys()),
        "has_compiled_release": isinstance(compiled, dict),
        "release_count": len(releases) if isinstance(releases, list) else None,
        "chosen_tag": chosen.get("tag"),
        "chosen_date": chosen.get("date"),
        "ocid": record.get("ocid") or chosen.get("ocid"),
        "tender_keys": sorted(tender.keys()),
        "tender_status": tender.get("status"),
        "main_category": tender.get("mainProcurementCategory"),
        "title": tender.get("title"),
        "deadline": period.get("endDate"),
        "value": value,
    }
    raise AssertionError(diagnostics)
