"""TEMPORARY live semantics probe for Germany DOE. Delete before merge."""
from __future__ import annotations

from collections import Counter
from io import BytesIO
import json
import zipfile
from xml.etree.ElementTree import fromstring

import requests

BASE = "https://oeffentlichevergabe.de"
EXPORTS = f"{BASE}/api/notice-exports"
ACCEPT = "application/vnd.bekanntmachungsservice.eforms.zip+zip"
DAY = "2026-08-23"
UA = "ObraSignal Germany DOE live semantics probe/1.0"


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    return "" if elem is None or elem.text is None else " ".join(str(elem.text).split())


def _desc(elem, name):
    return [x for x in elem.iter() if _local(x.tag) == name]


def _first(elem, name):
    for x in elem.iter():
        if _local(x.tag) == name:
            return x
    return None


def _first_text(elem, name):
    return _text(_first(elem, name))


def _direct_text(elem, name):
    if elem is None:
        return ""
    for x in list(elem):
        if _local(x.tag) == name:
            return _text(x)
    return ""


def _project_type(root):
    project = _first(root, "ProcurementProject")
    return _direct_text(project, "ProcurementTypeCode").lower()


def _lot_deadline(lot):
    for period in _desc(lot, "TenderSubmissionDeadlinePeriod"):
        return {"date": _direct_text(period, "EndDate"), "time": _direct_text(period, "EndTime")}
    return {}


def _cpvs(elem):
    out = []
    for node in _desc(elem, "ItemClassificationCode"):
        if (node.attrib.get("listName") or "").lower() in ("", "cpv") and _text(node):
            out.append(_text(node))
    return list(dict.fromkeys(out))


def _result_shape(result):
    values = []
    for node in result.iter():
        if node is result:
            continue
        value = _text(node)
        if value:
            values.append({"tag": _local(node.tag), "text": value[:300], "attrs": dict(list(node.attrib.items())[:8])})
    return values[:80]


def test_germany_doe_live_semantics():
    session = requests.Session()
    response = session.get(EXPORTS, params={"pubDay": DAY}, headers={"Accept": ACCEPT, "User-Agent": UA}, timeout=120)
    response.raise_for_status()
    assert response.content.startswith(b"PK")

    evidence = {
        "day": DAY,
        "zip_bytes": len(response.content),
        "content_disposition": response.headers.get("content-disposition"),
        "root_counts": {},
        "works_examples": [],
        "award_examples": [],
        "human_url": None,
    }
    roots = Counter()
    first_works_notice = ""

    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        evidence["entries"] = len(zf.infolist())
        for info in zf.infolist():
            if info.is_dir() or info.file_size > 4 * 1024 * 1024:
                continue
            root = fromstring(zf.read(info))
            root_name = _local(root.tag)
            roots[root_name] += 1

            if root_name == "ContractNotice" and _project_type(root) == "works" and len(evidence["works_examples"]) < 8:
                notice_id = _direct_text(root, "ID")
                folder = _direct_text(root, "ContractFolderID")
                lots = _desc(root, "ProcurementProjectLot")
                lot_rows = []
                for lot in lots:
                    lot_rows.append({
                        "id": _direct_text(lot, "ID"),
                        "deadline": _lot_deadline(lot),
                        "cpvs": _cpvs(lot),
                    })
                evidence["works_examples"].append({
                    "filename": info.filename,
                    "notice_id": notice_id,
                    "folder_id": folder,
                    "issue_date": _direct_text(root, "IssueDate"),
                    "issue_time": _direct_text(root, "IssueTime"),
                    "notice_type": _direct_text(root, "NoticeTypeCode"),
                    "project_cpvs": _cpvs(_first(root, "ProcurementProject")),
                    "lot_count": len(lots),
                    "unique_lot_ids": len({row["id"] for row in lot_rows if row["id"]}),
                    "lots": lot_rows[:12],
                })
                first_works_notice = first_works_notice or notice_id

            if root_name == "ContractAwardNotice" and len(evidence["award_examples"]) < 12:
                lot_results = _desc(root, "LotResult")
                if lot_results:
                    evidence["award_examples"].append({
                        "filename": info.filename,
                        "notice_id": _direct_text(root, "ID"),
                        "folder_id": _direct_text(root, "ContractFolderID"),
                        "project_type": _project_type(root),
                        "notice_type": _direct_text(root, "NoticeTypeCode"),
                        "lot_result_count": len(lot_results),
                        "results": [_result_shape(x) for x in lot_results[:5]],
                    })

    evidence["root_counts"] = dict(roots)

    if first_works_notice:
        url = f"{BASE}/ui/de/notices/{first_works_notice}"
        human = session.get(url, headers={"User-Agent": UA}, timeout=45, allow_redirects=True)
        evidence["human_url"] = {
            "requested": url,
            "status": human.status_code,
            "final_url": human.url,
            "content_type": human.headers.get("content-type"),
            "bytes": len(human.content),
            "has_notice_id": first_works_notice.lower() in human.text.lower(),
        }

    raise AssertionError("GERMANY_DOE_LIVE_SEMANTICS " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
