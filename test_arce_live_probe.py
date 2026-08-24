"""Temporary forensic probe for Uruguay ARCE OCDS Atom feed; remove after inspection."""
import xml.etree.ElementTree as ET

import requests

ARCE_RSS = "https://www.comprasestatales.gub.uy/ocds/rss"


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def test_arce_atom_shape_live():
    response = requests.get(
        ARCE_RSS,
        headers={
            "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
            "Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.1",
        },
        timeout=30,
    )
    assert response.status_code == 200, {
        "status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "server": response.headers.get("server"),
        "body_preview": response.text[:300],
    }
    assert "xml" in (response.headers.get("content-type") or "").lower(), response.headers
    root = ET.fromstring(response.content)
    assert _local(root.tag) == "feed", root.tag
    entries = [node for node in root if _local(node.tag) == "entry"]
    assert entries, "ARCE feed returned no entries"

    entry = entries[0]
    diagnostics = {
        "root_tag": root.tag,
        "entry_children": [_local(child.tag) for child in entry],
        "links": [child.attrib for child in entry if _local(child.tag) == "link"],
        "content_types": [child.attrib for child in entry if _local(child.tag) == "content"],
        "text_preview": { _local(child.tag): (child.text or "")[:200] for child in entry if (child.text or "").strip() },
    }
    raise AssertionError(diagnostics)
