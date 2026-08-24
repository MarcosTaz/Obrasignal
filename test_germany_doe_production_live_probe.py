"""TEMPORARY filename/root identity diagnostic for Germany DOE. Delete before merge."""
from __future__ import annotations

from collections import Counter
from io import BytesIO
import json
import re
import zipfile
from xml.etree.ElementTree import fromstring

import requests

URL = "https://oeffentlichevergabe.de/api/notice-exports"
ACCEPT = "application/vnd.bekanntmachungsservice.eforms.zip+zip"
DAY = "2026-08-23"
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}-\d+\.xml$")
SPLIT_RE = re.compile(r"^(?P<stem>.+)-(?P<version>\d+)\.xml$")


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(node):
    return "" if node is None or node.text is None else " ".join(str(node.text).split())


def _direct(root, name):
    for node in list(root):
        if _local(node.tag) == name:
            return node
    return None


def test_germany_doe_archive_filename_identity_live():
    response = requests.get(URL, params={"pubDay": DAY}, headers={"Accept": ACCEPT}, timeout=120)
    response.raise_for_status()
    patterns = Counter()
    mismatches, non_uuid, malformed = [], [], []

    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            match = SPLIT_RE.fullmatch(name)
            if not match:
                malformed.append(name)
                continue
            root = fromstring(zf.read(info))
            root_id = _text(_direct(root, "ID"))
            stem = match.group("stem")
            version = match.group("version")
            is_uuid = bool(UUID_RE.fullmatch(name))
            patterns["uuid" if is_uuid else "non_uuid"] += 1
            if stem != root_id:
                mismatches.append({
                    "filename": name,
                    "stem": stem,
                    "version": version,
                    "root": _local(root.tag),
                    "root_id": root_id,
                    "notice_type": _text(_direct(root, "NoticeTypeCode")),
                })
            if not is_uuid and len(non_uuid) < 40:
                non_uuid.append({
                    "filename": name,
                    "stem": stem,
                    "version": version,
                    "root": _local(root.tag),
                    "root_id": root_id,
                    "notice_type": _text(_direct(root, "NoticeTypeCode")),
                })

    evidence = {
        "entry_count": sum(patterns.values()) + len(malformed),
        "patterns": dict(patterns),
        "malformed_count": len(malformed),
        "malformed": malformed[:40],
        "stem_root_mismatch_count": len(mismatches),
        "stem_root_mismatches": mismatches[:40],
        "non_uuid_examples": non_uuid,
    }
    raise AssertionError("GERMANY_DOE_FILENAME_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:160000])
