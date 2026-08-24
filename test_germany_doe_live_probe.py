"""TEMPORARY Germany DOE direct-ID/human-route probe. Delete before merge."""
from __future__ import annotations

from io import BytesIO
import json
import zipfile
from xml.etree.ElementTree import fromstring

import requests

BASE = "https://oeffentlichevergabe.de"
EXPORTS = f"{BASE}/api/notice-exports"
EFORMS = "application/vnd.bekanntmachungsservice.eforms.zip+zip"
DAY = "2026-08-23"
UA = "ObraSignal Germany DOE forensic probe/3.0"


def local(tag):
    return str(tag).rsplit("}", 1)[-1]


def text(elem):
    return "" if elem is None or elem.text is None else " ".join(str(elem.text).split())


def direct(elem, name):
    for child in list(elem):
        if local(child.tag) == name:
            return child
    return None


def first_desc(elem, name):
    for child in elem.iter():
        if child is not elem and local(child.tag) == name:
            return child
    return None


def test_germany_doe_direct_identity_live():
    session = requests.Session()
    response = session.get(EXPORTS, params={"pubDay": DAY}, headers={"Accept": EFORMS, "User-Agent": UA}, timeout=90)
    assert response.status_code == 200 and response.content.startswith(b"PK")
    zf = zipfile.ZipFile(BytesIO(response.content))
    evidence = {"day": DAY, "entries": len(zf.namelist()), "works": []}
    for name in zf.namelist():
        if not name.endswith(".xml"):
            continue
        root = fromstring(zf.read(name))
        if local(root.tag) != "ContractNotice":
            continue
        project = first_desc(root, "ProcurementProject")
        proc_type = text(direct(project, "ProcurementTypeCode")).lower() if project is not None else ""
        if proc_type != "works":
            continue
        root_id = text(direct(root, "ID"))
        folder_id = text(direct(root, "ContractFolderID"))
        issue_date = text(direct(root, "IssueDate"))
        issue_time = text(direct(root, "IssueTime"))
        filename_uuid = name[:-4].rsplit("-", 1)[0]
        lots = []
        for lot in (e for e in root.iter() if local(e.tag) == "ProcurementProjectLot"):
            lot_id = text(direct(lot, "ID"))
            process = direct(lot, "TenderingProcess")
            period = direct(process, "TenderSubmissionDeadlinePeriod") if process is not None else None
            lots.append({
                "lot_id": lot_id,
                "end_date": text(direct(period, "EndDate")) if period is not None else "",
                "end_time": text(direct(period, "EndTime")) if period is not None else "",
            })
        human = f"{BASE}/ui/de/notices/{root_id}" if root_id else ""
        human_response = session.get(human, headers={"User-Agent": UA}, timeout=30) if human else None
        evidence["works"].append({
            "file": name,
            "filename_uuid": filename_uuid,
            "root_id": root_id,
            "root_matches_filename": root_id == filename_uuid,
            "contract_folder_id": folder_id,
            "issue_date": issue_date,
            "issue_time": issue_time,
            "lots": lots,
            "human_url": human,
            "human_status": human_response.status_code if human_response is not None else None,
        })
        if len(evidence["works"]) >= 3:
            break
    assert evidence["works"]
    raise AssertionError("GERMANY_DOE_ID_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:80000])
