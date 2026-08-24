"""TEMPORARY diagnostic for Germany DOE Works award families. Delete before merge."""
from __future__ import annotations

from collections import Counter
from io import BytesIO
import json
import zipfile
from xml.etree.ElementTree import fromstring

import requests

URL = "https://oeffentlichevergabe.de/api/notice-exports"
ACCEPT = "application/vnd.bekanntmachungsservice.eforms.zip+zip"
DAY = "2026-08-23"


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(node):
    return "" if node is None or node.text is None else " ".join(str(node.text).split())


def _desc(root, name):
    return [node for node in root.iter() if _local(node.tag) == name]


def _direct(root, name):
    for node in list(root):
        if _local(node.tag) == name:
            return node
    return None


def _direct_text(root, name):
    return _text(_direct(root, name))


def _first(root, name):
    for node in root.iter():
        if _local(node.tag) == name:
            return node
    return None


def _project_type(root):
    project = _first(root, "ProcurementProject")
    return _direct_text(project, "ProcurementTypeCode").lower() if project is not None else ""


def _shape(result):
    out = []
    for node in result.iter():
        if node is result:
            continue
        value = _text(node)
        if value:
            out.append({"tag": _local(node.tag), "text": value[:300], "attrs": dict(node.attrib)})
    return out[:120]


def test_germany_doe_missing_result_status_live():
    response = requests.get(URL, params={"pubDay": DAY}, headers={"Accept": ACCEPT}, timeout=120)
    response.raise_for_status()
    missing, works_total, code_counts = [], 0, Counter()

    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            root = fromstring(zf.read(info))
            if _local(root.tag) != "ContractAwardNotice" or _project_type(root) != "works":
                continue
            works_total += 1
            results = _desc(root, "LotResult")
            codes = []
            for result in results:
                code = _text(_direct(result, "TenderResultCode"))
                code_counts[code or "<missing>"] += 1
                codes.append(code)
            if not results or any(not code for code in codes):
                missing.append({
                    "filename": info.filename,
                    "notice_id": _direct_text(root, "ID"),
                    "folder_id": _direct_text(root, "ContractFolderID"),
                    "notice_type": _direct_text(root, "NoticeTypeCode"),
                    "issue_date": _direct_text(root, "IssueDate"),
                    "issue_time": _direct_text(root, "IssueTime"),
                    "lot_result_count": len(results),
                    "result_codes": codes,
                    "results": [_shape(result) for result in results[:6]],
                })

    evidence = {
        "day": DAY,
        "works_award_notice_count": works_total,
        "winner_status_counts": dict(code_counts),
        "missing_count": len(missing),
        "missing_examples": missing[:30],
    }
    raise AssertionError("GERMANY_DOE_MISSING_STATUS_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
