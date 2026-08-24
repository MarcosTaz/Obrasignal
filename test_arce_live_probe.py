"""Temporary forensic probe for Uruguay ARCE OCDS Atom feed; remove after inspection."""
import xml.etree.ElementTree as ET

import requests

ARCE_RSS = "https://www.comprasestatales.gub.uy/ocds/rss"


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def test_arce_atom_shape_live():
    response = requests.get(ARCE_RSS, timeout=30)
    response.raise_for_status()
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
