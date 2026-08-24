"""Temporary forensic probe for Uruguay ARCE OCDS RSS feed; remove after inspection."""
import xml.etree.ElementTree as ET

import requests

ARCE_RSS = "https://www.comprasestatales.gub.uy/ocds/rss"
HEADERS = {
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.1",
}


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def test_arce_rss_item_shape_live():
    response = requests.get(ARCE_RSS, headers=HEADERS, timeout=30)
    assert response.status_code == 200, {
        "status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "body_preview": response.text[:300],
    }
    root = ET.fromstring(response.content)
    assert _local(root.tag) == "rss", root.tag
    channel = next((node for node in root if _local(node.tag) == "channel"), None)
    assert channel is not None, [_local(node.tag) for node in root]
    items = [node for node in channel if _local(node.tag) == "item"]
    assert items, "ARCE RSS returned no items"

    item = items[0]
    diagnostics = {
        "channel_children": [_local(child.tag) for child in channel[:12]],
        "item_children": [_local(child.tag) for child in item],
        "item_attrs": { _local(child.tag): child.attrib for child in item if child.attrib },
        "item_text": { _local(child.tag): (child.text or "")[:500] for child in item if (child.text or "").strip() },
    }
    raise AssertionError(diagnostics)
