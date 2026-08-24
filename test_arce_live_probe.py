"""Temporary forensic probe for Uruguay ARCE release-field evolution; remove after inspection."""
import re
import time
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


def test_arce_release_field_evolution_live():
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
    refs = sorted(
        [ref for ref in (record.get("releases") or []) if isinstance(ref, dict) and ref.get("url")],
        key=lambda ref: str(ref.get("date") or ""),
    )
    assert refs and len(refs) <= 25, len(refs)

    evolution = []
    for ref in refs:
        time.sleep(0.12)
        url = str(ref["url"]).replace("http://", "https://", 1)
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        release_package = response.json()
        releases = release_package.get("releases") if isinstance(release_package, dict) else None
        assert isinstance(releases, list) and releases, {"url": url, "keys": getattr(release_package, "keys", lambda: [])()}
        release = releases[0]
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
        value = tender.get("value") if isinstance(tender.get("value"), dict) else {}
        evolution.append({
            "ref_date": ref.get("date"),
            "tag": release.get("tag"),
            "release_id": release.get("id"),
            "tender_keys": sorted(tender.keys()),
            "status": tender.get("status") if "status" in tender else "<absent>",
            "title": tender.get("title") if "title" in tender else "<absent>",
            "category": tender.get("mainProcurementCategory") if "mainProcurementCategory" in tender else "<absent>",
            "deadline": period.get("endDate") if "endDate" in period else "<absent>",
            "value": value if value else "<absent>",
            "items_count": len(tender.get("items") or []) if "items" in tender else "<absent>",
        })

    raise AssertionError({
        "purchase_id": purchase_id,
        "ocid": record.get("ocid"),
        "release_count": len(refs),
        "evolution": evolution,
    })
