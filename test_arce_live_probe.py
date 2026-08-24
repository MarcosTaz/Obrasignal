"""Temporary forensic probe for Uruguay ARCE OCDS RSS/release contract; remove after inspection."""
import xml.etree.ElementTree as ET

import requests

ARCE_RSS = "https://www.comprasestatales.gub.uy/ocds/rss"
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


def test_arce_tender_release_contract_live():
    response = requests.get(ARCE_RSS, headers=HEADERS, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    channel = next(node for node in root if _local(node.tag) == "channel")
    items = [node for node in channel if _local(node.tag) == "item"]
    categories = [_text(item, "category") for item in items]
    tender_items = [item for item in items if "tender" in _text(item, "category").lower()]
    assert tender_items, {"categories": sorted(set(categories))[:50], "count": len(items)}

    item = tender_items[0]
    link = _text(item, "link")
    assert "/ocds/release/" in link, link
    detail = requests.get(link.replace("http://", "https://", 1), headers=HEADERS, timeout=30)
    detail.raise_for_status()
    package = detail.json()
    assert isinstance(package, dict), type(package)
    releases = package.get("releases")
    assert isinstance(releases, list) and releases, package.keys()
    release = releases[0]
    diagnostics = {
        "rss_category": _text(item, "category"),
        "rss_pubDate": _text(item, "pubDate"),
        "rss_guid": _text(item, "guid"),
        "rss_link": link,
        "package_keys": sorted(package.keys()),
        "release_keys": sorted(release.keys()),
        "release_tag": release.get("tag"),
        "release_date": release.get("date"),
        "ocid": release.get("ocid"),
        "tender_keys": sorted((release.get("tender") or {}).keys()),
        "tender_status": (release.get("tender") or {}).get("status"),
        "main_category": (release.get("tender") or {}).get("mainProcurementCategory"),
    }
    raise AssertionError(diagnostics)
