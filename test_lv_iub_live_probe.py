"""Temporary forensic probe for Latvia IUB daily JSON bulk semantics; delete after contract freeze."""
from collections import Counter
from datetime import date, timedelta

import requests

ROOT = "https://open.iub.gov.lv/data/notice"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
}


def _summary(value, depth=0, limit=60):
    if depth >= 4:
        if isinstance(value, (dict, list)):
            return {"type": type(value).__name__, "length": len(value)}
        return value
    if isinstance(value, dict):
        return {key: _summary(val, depth + 1, limit) for key, val in list(value.items())[:limit]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first": _summary(value[0], depth + 1, limit) if value else None,
        }
    text = str(value) if value is not None else None
    return text[:500] if isinstance(text, str) else text


def _url(day):
    return f"{ROOT}/{day:%Y/%m/%d-%m-%Y}.json"


def _find_latest_file():
    today = date(2026, 8, 24)
    attempts = []
    for offset in range(1, 8):
        day = today - timedelta(days=offset)
        result = requests.get(_url(day), headers=HEADERS, timeout=30)
        attempts.append((result.url, result.status_code, len(result.content)))
        if result.status_code == 200 and result.content.strip():
            return day, result, attempts
    raise AssertionError({"attempts": attempts})


def _deadline_candidates(record):
    rows = []
    process = record.get("tenderingProcess") if isinstance(record.get("tenderingProcess"), dict) else {}
    for key, value in process.items():
        if "deadline" in key.lower() and value:
            rows.append((f"tenderingProcess.{key}", value))
    lots = record.get("lots") if isinstance(record.get("lots"), list) else []
    for index, lot in enumerate(lots):
        if not isinstance(lot, dict):
            continue
        for container_name in ("tenderingProcess", "tenderingTerms", "additionalInformation"):
            container = lot.get(container_name) if isinstance(lot.get(container_name), dict) else {}
            for key, value in container.items():
                if "deadline" in key.lower() and value:
                    rows.append((f"lots[{index}].{container_name}.{key}", value))
    return rows


def _interesting(record):
    lots = record.get("lots") if isinstance(record.get("lots"), list) else []
    return {
        "identifier": record.get("identifier"),
        "previousIdentifier": record.get("previousIdentifier"),
        "clonedFrom": record.get("clonedFrom"),
        "name": record.get("name"),
        "noticeType": record.get("noticeType"),
        "formType": record.get("formType"),
        "cpvType": record.get("cpvType"),
        "mainNatureType": record.get("mainNatureType"),
        "procurementProject": _summary(record.get("procurementProject")),
        "tenderingProcess": _summary(record.get("tenderingProcess")),
        "organizationData": _summary(record.get("organizationData")),
        "tenderingTerms": _summary(record.get("tenderingTerms")),
        "automaticallyCalculated": _summary(record.get("automaticallyCalculated")),
        "deadlines": _deadline_candidates(record),
        "lots_count": len(lots),
        "first_lot": _summary(lots[0]) if lots else None,
        "documents_url": (record.get("tenderingProcess") or {}).get("documentsURL") if isinstance(record.get("tenderingProcess"), dict) else None,
    }


def test_lv_iub_current_daily_json_semantics_live():
    selected, response, attempts = _find_latest_file()
    payload = response.json()
    assert isinstance(payload, list), type(payload)
    records = [row for row in payload if isinstance(row, dict)]
    assert records

    form_counts = Counter(str(row.get("formType")) for row in records)
    notice_counts = Counter(str(row.get("noticeType")) for row in records)
    nature_counts = Counter(
        str(
            row.get("mainNatureType")
            or ((row.get("procurementProject") or {}).get("mainNatureType") if isinstance(row.get("procurementProject"), dict) else None)
        )
        for row in records
    )
    with_deadline = [row for row in records if _deadline_candidates(row)]
    clones = [row for row in records if row.get("clonedFrom")]
    works = [
        row for row in records
        if str(
            row.get("mainNatureType")
            or ((row.get("procurementProject") or {}).get("mainNatureType") if isinstance(row.get("procurementProject"), dict) else "")
        ).lower() == "works"
    ]
    competitions = [row for row in records if str(row.get("formType") or "").lower() == "competition"]

    diagnostics = {
        "selected_day": selected.isoformat(),
        "url": response.url,
        "bytes": len(response.content),
        "record_count": len(records),
        "form_counts": dict(form_counts),
        "notice_counts": dict(notice_counts),
        "nature_counts": dict(nature_counts),
        "deadline_record_count": len(with_deadline),
        "clone_count": len(clones),
        "works_count": len(works),
        "competition_count": len(competitions),
        "first_record": _interesting(records[0]),
        "first_with_deadline": _interesting(with_deadline[0]) if with_deadline else None,
        "first_clone": _interesting(clones[0]) if clones else None,
        "first_works": _interesting(works[0]) if works else None,
        "attempts": attempts,
    }
    raise AssertionError(diagnostics)
