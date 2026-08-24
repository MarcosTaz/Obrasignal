"""Temporary forensic probe for Uruguay ARCE OCDS release-history semantics; remove after inspection."""
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


def test_arce_release_history_field_semantics_live():
    response = requests.get(ARCE_RSS, headers=HEADERS, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    channel = next(node for node in root if _local(node.tag) == "channel")
    items = [node for node in channel if _local(node.tag) == "item"]
    tender_items = [item for item in items if "tender" in _text(item, "category").lower()]
    assert tender_items
    item = tender_items[0]
    purchase_id = _purchase_id(_text(item, "title"))
    assert purchase_id

    detail = requests.get(f"{ARCE_RECORD_ROOT}/{purchase_id}", headers=HEADERS, timeout=30)
    detail.raise_for_status()
    package = detail.json()
    records = package.get("records") if isinstance(package, dict) else None
    assert isinstance(records, list) and records
    record = records[0]
    releases = sorted(
        [release for release in (record.get("releases") or []) if isinstance(release, dict)],
        key=lambda release: str(release.get("date") or ""),
    )
    assert releases

    timeline = []
    for release in releases:
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
        value = tender.get("value") if isinstance(tender.get("value"), dict) else {}
        timeline.append({
            "date": release.get("date"),
            "tag": release.get("tag"),
            "id": release.get("id"),
            "keys": sorted(tender.keys()),
            "status": tender.get("status") if "status" in tender else "<absent>",
            "title": tender.get("title") if "title" in tender else "<absent>",
            "category": tender.get("mainProcurementCategory") if "mainProcurementCategory" in tender else "<absent>",
            "deadline": period.get("endDate") if "endDate" in period else "<absent>",
            "value": value if value else "<absent>",
            "items": len(tender.get("items") or []) if "items" in tender else "<absent>",
        })

    latest_explicit = {}
    for field in ("status", "title", "mainProcurementCategory", "tenderPeriod", "value", "items"):
        for release in reversed(releases):
            tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
            if field in tender:
                latest_explicit[field] = {"date": release.get("date"), "tag": release.get("tag"), "value": tender.get(field)}
                break

    raise AssertionError({
        "purchase_id": purchase_id,
        "ocid": record.get("ocid"),
        "release_count": len(releases),
        "timeline": timeline,
        "latest_explicit": latest_explicit,
    })
