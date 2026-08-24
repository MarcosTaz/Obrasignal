"""TEMPORARY live probe for Estonia RHR eForms semantics. Delete before merge."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from xml.etree.ElementTree import XMLPullParser

import requests


BASE = "https://riigihanked.riik.ee/rhr/api/public/v1/opendata"
HEADERS = {
    "User-Agent": "ObraSignal RHR live validation/1.0",
    "Accept": "application/xml,text/xml,*/*",
}
MAX_RESOURCE_BYTES = 55 * 1024 * 1024


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _text(elem):
    return "" if elem is None or elem.text is None else " ".join(elem.text.split())


def _direct(elem, name):
    for child in list(elem):
        if _local(child.tag) == name:
            return child
    return None


def _direct_text(elem, name):
    return _text(_direct(elem, name))


def _first_desc(elem, name):
    for child in elem.iter():
        if child is not elem and _local(child.tag) == name:
            return child
    return None


def _desc_texts(elem, name):
    values = []
    for child in elem.iter():
        if _local(child.tag) == name:
            value = _text(child)
            if value:
                values.append(value)
    return values


def _walk(elem, path=""):
    here = f"{path}/{_local(elem.tag)}"
    yield here, elem
    for child in list(elem):
        yield from _walk(child, here)


def _deadline_evidence(elem):
    rows = []
    seen = set()
    for path, child in _walk(elem):
        local = _local(child.tag)
        low_path = path.lower()
        interesting = (
            "deadline" in local.lower()
            or "submission" in local.lower()
            or (local in {"EndDate", "EndTime"} and ("tender" in low_path or "submission" in low_path))
            or local in {"ReceiptDeadlinePeriod", "TenderSubmissionDeadlinePeriod"}
        )
        if not interesting:
            continue
        value = _text(child)
        if not value and local not in {"ReceiptDeadlinePeriod", "TenderSubmissionDeadlinePeriod"}:
            continue
        key = (path, value)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"path": path[-240:], "tag": local, "text": value[:240]})
        if len(rows) >= 30:
            break
    return rows


def _cpvs(elem):
    values = []
    for child in elem.iter():
        if _local(child.tag) != "ItemClassificationCode":
            continue
        if child.attrib.get("listName") not in (None, "cpv"):
            continue
        value = _text(child)
        if value and value not in values:
            values.append(value)
    return values[:20]


def _human_uris(elem):
    values = []
    for child in elem.iter():
        if _local(child.tag) not in {"URI", "WebsiteURI", "BuyerProfileURI"}:
            continue
        value = _text(child)
        if "riigihanked.riik.ee/rhr-web/#/procurement/" in value and value not in values:
            values.append(value)
    return values[:10]


def _lot_summary(elem):
    lots = []
    for lot in elem.iter():
        if _local(lot.tag) != "ProcurementProjectLot":
            continue
        row = {
            "id": _direct_text(lot, "ID"),
            "name": _direct_text(lot, "Name"),
            "procurement_type": _direct_text(lot, "ProcurementTypeCode"),
            "cpvs": _cpvs(lot),
            "deadlines": _deadline_evidence(lot),
        }
        lots.append(row)
        if len(lots) >= 12:
            break
    return lots


def _notice_summary(elem):
    project = _first_desc(elem, "ProcurementProject")
    project_type = _direct_text(project, "ProcurementTypeCode") if project is not None else ""
    project_id = _direct_text(project, "ID") if project is not None else ""
    return {
        "root": _local(elem.tag),
        "notice_id": _direct_text(elem, "ID"),
        "contract_folder_id": _direct_text(elem, "ContractFolderID"),
        "version": _direct_text(elem, "VersionID"),
        "issue_date": _direct_text(elem, "IssueDate"),
        "issue_time": _direct_text(elem, "IssueTime"),
        "notice_type": _direct_text(elem, "NoticeTypeCode"),
        "project_id": project_id,
        "project_name": _direct_text(project, "Name") if project is not None else "",
        "project_type": project_type,
        "cpvs": _cpvs(project) if project is not None else [],
        "deadlines": _deadline_evidence(elem),
        "lots": _lot_summary(elem),
        "human_uris": _human_uris(elem),
    }


def _stream_notices(session, url, expected_root, on_notice):
    response = session.get(url, headers=HEADERS, timeout=90, stream=True, allow_redirects=True)
    response.raise_for_status()
    content_length = int(response.headers.get("content-length") or 0)
    if content_length and content_length > MAX_RESOURCE_BYTES:
        response.close()
        raise AssertionError(f"resource too large for bounded probe: {content_length}")

    parser = XMLPullParser(events=("end",))
    received = 0
    count = 0
    try:
        for chunk in response.iter_content(chunk_size=131072):
            if not chunk:
                continue
            received += len(chunk)
            if received > MAX_RESOURCE_BYTES:
                raise AssertionError("resource exceeded probe byte hard limit")
            parser.feed(chunk)
            for _event, elem in parser.read_events():
                if _local(elem.tag) != expected_root:
                    continue
                count += 1
                stop = on_notice(elem)
                elem.clear()
                if stop:
                    return {
                        "status": response.status_code,
                        "content_length": content_length,
                        "received": received,
                        "notices_seen": count,
                        "stopped_early": True,
                    }
    finally:
        response.close()
    return {
        "status": response.status_code,
        "content_length": content_length,
        "received": received,
        "notices_seen": count,
        "stopped_early": False,
    }


def test_estonia_rhr_works_versions_and_award_link_live():
    session = requests.Session()
    evidence = {"at": datetime.now(timezone.utc).isoformat(), "notice_scans": {}}
    works = []
    folders = defaultdict(list)
    projects = defaultdict(list)

    def observe_notice(elem):
        summary = _notice_summary(elem)
        folder = summary["contract_folder_id"]
        project = summary["project_id"]
        identity = {
            key: summary[key]
            for key in ("notice_id", "contract_folder_id", "version", "issue_date", "notice_type", "project_id", "project_type")
        }
        if folder:
            folders[folder].append(identity)
        if project:
            projects[project].append(identity)
        if summary["project_type"] == "works":
            works.append(summary)
        # Scan the complete month so version pairs can be detected; resource is
        # bounded by MAX_RESOURCE_BYTES and August is only ~20 MB.
        return False

    for year, month in ((2026, 8), (2026, 7)):
        url = f"{BASE}/notice/{year}/month/{month}/xml"
        evidence["notice_scans"][f"{year}-{month:02d}"] = _stream_notices(
            session, url, "ContractNotice", observe_notice
        )
        if len(works) >= 3 and any(len(v) >= 2 for v in folders.values()):
            break

    evidence["works"] = works[:5]
    evidence["folder_version_pairs"] = [
        rows[:8] for rows in folders.values()
        if len({(row["notice_id"], row["version"]) for row in rows}) >= 2
    ][:8]
    evidence["project_version_pairs"] = [
        rows[:8] for rows in projects.values()
        if len({(row["notice_id"], row["version"]) for row in rows}) >= 2
    ][:8]

    # Try to link awards using identities from observed Works notices. We do not
    # assume ContractFolderID is shared until a live award proves it.
    target_folders = {row["contract_folder_id"] for row in works if row["contract_folder_id"]}
    target_projects = {row["project_id"] for row in works if row["project_id"]}
    award_matches = []
    award_examples = []

    def observe_award(elem):
        summary = _notice_summary(elem)
        if len(award_examples) < 3:
            award_examples.append(summary)
        folder = summary["contract_folder_id"]
        project = summary["project_id"]
        if (folder and folder in target_folders) or (project and project in target_projects):
            award_matches.append(summary)
        return len(award_matches) >= 2

    evidence["award_scans"] = {}
    if target_folders or target_projects:
        for year, month in ((2026, 8), (2026, 7)):
            url = f"{BASE}/notice_award/{year}/month/{month}/xml"
            evidence["award_scans"][f"{year}-{month:02d}"] = _stream_notices(
                session, url, "ContractAwardNotice", observe_award
            )
            if len(award_matches) >= 2:
                break
    evidence["award_matches"] = award_matches[:3]
    evidence["award_examples"] = award_examples[:3]

    assert works, "No live RHR ProcurementTypeCode=works notice found"
    raise AssertionError("EE_RHR_SEMANTICS " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:60000])
