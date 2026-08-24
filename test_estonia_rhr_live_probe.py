"""TEMPORARY live probe for Estonia RHR lot/republication semantics. Delete before merge."""
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


def _cpvs(elem):
    values = []
    if elem is None:
        return values
    for child in elem.iter():
        if _local(child.tag) == "ItemClassificationCode" and child.attrib.get("listName") in (None, "cpv"):
            value = _text(child)
            if value and value not in values:
                values.append(value)
    return values[:20]


def _deadline(lot):
    if lot is None:
        return None
    for process in lot.iter():
        if _local(process.tag) != "TenderSubmissionDeadlinePeriod":
            continue
        date = _direct_text(process, "EndDate")
        time = _direct_text(process, "EndTime")
        return {"date": date, "time": time}
    return None


def _human_uri(elem):
    for child in elem.iter():
        if _local(child.tag) != "URI":
            continue
        value = _text(child)
        if "riigihanked.riik.ee/rhr-web/#/procurement/" in value:
            return value
    return ""


def _lots(elem):
    rows = []
    for lot in elem.iter():
        if _local(lot.tag) != "ProcurementProjectLot":
            continue
        rows.append({
            "id": _direct_text(lot, "ID"),
            "deadline": _deadline(lot),
            "cpvs": _cpvs(lot),
        })
    return rows


def _notice(elem):
    project = _first_desc(elem, "ProcurementProject")
    return {
        "notice_id": _direct_text(elem, "ID"),
        "folder": _direct_text(elem, "ContractFolderID"),
        "version": _direct_text(elem, "VersionID"),
        "issue_date": _direct_text(elem, "IssueDate"),
        "issue_time": _direct_text(elem, "IssueTime"),
        "notice_type": _direct_text(elem, "NoticeTypeCode"),
        "project_id": _direct_text(project, "ID") if project is not None else "",
        "project_name": _direct_text(project, "Name") if project is not None else "",
        "project_type": _direct_text(project, "ProcurementTypeCode") if project is not None else "",
        "cpvs": _cpvs(project),
        "lots": _lots(elem),
        "human_uri": _human_uri(elem),
    }


def _award_lot_results(elem):
    results = []
    for result in elem.iter():
        if _local(result.tag) != "LotResult":
            continue
        lot_ids = []
        contract_ids = []
        tender_ids = []
        for child in result.iter():
            local = _local(child.tag)
            value = _text(child)
            if not value:
                continue
            if local == "ID" and child.attrib.get("schemeName") == "Lot" and value not in lot_ids:
                lot_ids.append(value)
            elif local == "ID" and child.attrib.get("schemeName") == "contract" and value not in contract_ids:
                contract_ids.append(value)
            elif local == "ID" and child.attrib.get("schemeName") == "tender" and value not in tender_ids:
                tender_ids.append(value)
        results.append({
            "result_id": _direct_text(result, "ID"),
            "tender_result_code": _direct_text(result, "TenderResultCode"),
            "lot_ids": lot_ids,
            "contract_ids": contract_ids,
            "tender_ids": tender_ids,
        })
    return results


def _stream(session, url, root_name, callback):
    response = session.get(url, headers=HEADERS, timeout=90, stream=True, allow_redirects=True)
    response.raise_for_status()
    size = int(response.headers.get("content-length") or 0)
    if size and size > MAX_RESOURCE_BYTES:
        response.close()
        raise AssertionError(f"RHR resource too large: {size}")
    parser = XMLPullParser(events=("end",))
    received = count = 0
    try:
        for chunk in response.iter_content(chunk_size=131072):
            if not chunk:
                continue
            received += len(chunk)
            if received > MAX_RESOURCE_BYTES:
                raise AssertionError("RHR resource exceeded byte hard limit")
            parser.feed(chunk)
            for _event, elem in parser.read_events():
                if _local(elem.tag) != root_name:
                    continue
                count += 1
                stop = callback(elem)
                elem.clear()
                if stop:
                    return {"bytes": received, "count": count, "stopped_early": True}
    finally:
        response.close()
    return {"bytes": received, "count": count, "stopped_early": False}


def test_estonia_rhr_lots_republication_and_award_semantics_live():
    session = requests.Session()
    evidence = {"at": datetime.now(timezone.utc).isoformat()}
    by_folder = defaultdict(list)
    multi_lot_works = []
    all_works_folders = set()

    def notice_cb(elem):
        row = _notice(elem)
        if row["project_type"] != "works":
            return False
        all_works_folders.add(row["folder"])
        by_folder[row["folder"]].append(row)
        if len(row["lots"]) > 1 and len(multi_lot_works) < 5:
            multi_lot_works.append(row)
        return False

    notice_scans = {}
    for year, month in ((2026, 8), (2026, 7)):
        notice_scans[f"{year}-{month:02d}"] = _stream(
            session,
            f"{BASE}/notice/{year}/month/{month}/xml",
            "ContractNotice",
            notice_cb,
        )
    evidence["notice_scans"] = notice_scans

    repeated = []
    for folder, rows in by_folder.items():
        unique = {row["notice_id"]: row for row in rows if row["notice_id"]}
        if len(unique) < 2:
            continue
        ordered = sorted(unique.values(), key=lambda r: (r["issue_date"], r["issue_time"], r["notice_id"]))
        repeated.append({
            "folder": folder,
            "project_id": ordered[-1]["project_id"],
            "republications": ordered[:8],
        })
        if len(repeated) >= 8:
            break
    evidence["repeated_works"] = repeated
    evidence["multi_lot_works"] = multi_lot_works

    award_matches = []
    award_result_codes = defaultdict(int)

    def award_cb(elem):
        row = _notice(elem)
        if row["project_type"] != "works":
            return False
        for result in _award_lot_results(elem):
            award_result_codes[result["tender_result_code"]] += 1
        if row["folder"] in all_works_folders and len(award_matches) < 5:
            row["lot_results"] = _award_lot_results(elem)
            award_matches.append(row)
        return len(award_matches) >= 5

    award_scans = {}
    for year, month in ((2026, 8), (2026, 7)):
        award_scans[f"{year}-{month:02d}"] = _stream(
            session,
            f"{BASE}/notice_award/{year}/month/{month}/xml",
            "ContractAwardNotice",
            award_cb,
        )
        if len(award_matches) >= 5:
            break
    evidence["award_scans"] = award_scans
    evidence["award_matches"] = award_matches
    evidence["award_result_codes"] = dict(sorted(award_result_codes.items()))

    assert repeated, "No repeated Works ContractFolderID found"
    assert multi_lot_works, "No multi-lot Works notice found"
    assert award_matches, "No Works award matched by ContractFolderID"
    raise AssertionError("EE_RHR_LOTS " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:65000])
