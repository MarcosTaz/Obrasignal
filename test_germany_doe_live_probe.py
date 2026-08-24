"""TEMPORARY Germany DÖE lifecycle/version probe. Delete before merge."""
from __future__ import annotations

from collections import Counter
import io
import json
import re
import zipfile

import requests

EXPORT_URL = "https://oeffentlichevergabe.de/api/notice-exports"
DETAIL_BASE = "https://oeffentlichevergabe.de/api/notices"
HUMAN_BASE = "https://oeffentlichevergabe.de/ui/de/notices"
PUB_DAY = "2026-08-21"
MAX_BYTES = 120 * 1024 * 1024
MAX_FILES = 2000
MAX_DETAILS = 8
UA = "ObraSignal Germany DÖE forensic probe/2.0"


def _download(session, url, *, params=None):
    response = session.get(url, params=params, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=90, stream=True)
    chunks, total = [], 0
    for chunk in response.iter_content(1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_BYTES:
            raise RuntimeError(f"DÖE probe exceeded {MAX_BYTES} bytes")
        chunks.append(chunk)
    return response, b"".join(chunks)


def _file_identity(name):
    base = re.sub(r"\.(json|xml)$", "", name.rsplit("/", 1)[-1], flags=re.I)
    match = re.match(r"^(.+?)-(\d+)$", base)
    return (match.group(1), int(match.group(2))) if match else (base, 0)


def _tags(release):
    value = release.get("tag") if isinstance(release, dict) else None
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if value:
        return (str(value).strip(),)
    return ()


def _compact_release(name, release):
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    notice_id, version = _file_identity(name)
    return {
        "file": name,
        "notice_id": notice_id,
        "file_version": version,
        "release_id": release.get("id"),
        "ocid": release.get("ocid"),
        "date": release.get("date"),
        "tag": list(_tags(release)),
        "tender_id": tender.get("id"),
        "title": tender.get("title"),
        "status": tender.get("status"),
        "category": tender.get("mainProcurementCategory"),
        "lot_ids": [lot.get("id") for lot in tender.get("lots", []) if isinstance(lot, dict)][:12],
    }


def _simple(value):
    if isinstance(value, dict):
        return {str(k): _simple(v) for k, v in list(value.items())[:25] if isinstance(v, (str, int, float, bool, type(None), dict, list))}
    if isinstance(value, list):
        return [_simple(v) for v in value[:12]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _detail_summary(payload):
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    lots = payload.get("lots") if isinstance(payload.get("lots"), list) else []
    lot_rows = []
    for lot in lots[:12]:
        if not isinstance(lot, dict):
            continue
        terms = lot.get("submissionTerms") if isinstance(lot.get("submissionTerms"), dict) else {}
        lot_rows.append({
            "id": lot.get("id"),
            "cpv": _simple(lot.get("classification")),
            "deadlineReceiptTenders": terms.get("deadlineReceiptTenders"),
            "deadlineReceiptRequests": terms.get("deadlineReceiptRequests"),
            "submissionUrl": terms.get("submissionUrl"),
        })
    return {
        "noticeIdentifier": payload.get("noticeIdentifier"),
        "originalNoticeIdentifier": payload.get("originalNoticeIdentifier"),
        "procedureIdentifier": payload.get("procedureIdentifier"),
        "noticeVersion": payload.get("noticeVersion"),
        "noticeType": _simple(payload.get("noticeType")),
        "noticeSubType": _simple(payload.get("noticeSubType")),
        "publicationDate": payload.get("publicationDate"),
        "issueDateTime": payload.get("issueDateTime"),
        "changeDate": payload.get("changeDate"),
        "classification": _simple(payload.get("classification")),
        "purpose": _simple(payload.get("purpose")),
        "procedure": _simple(payload.get("procedure")),
        "lots": lot_rows,
        "lot_count": len(lots),
    }


def test_germany_doe_lifecycle_versions_live():
    s = requests.Session()
    evidence = {"export": {}, "tag_counts": {}, "works_tag_counts": {}, "version_counts": {}, "candidates": {}, "details": []}
    response, blob = _download(s, EXPORT_URL, params={"pubDay": PUB_DAY, "format": "ocds.zip"})
    assert response.status_code == 200 and blob[:4] == b"PK\x03\x04"
    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = [name for name in archive.namelist() if name.lower().endswith(".json")]
    assert names and len(names) <= MAX_FILES
    evidence["export"] = {"status": response.status_code, "received": len(blob), "file_count": len(names), "first_names": names[:10]}

    tag_counts, works_tag_counts, version_counts = Counter(), Counter(), Counter()
    versioned_works, terminal_works, tender_works = [], [], []
    all_works = []
    for name in names:
        try:
            payload = json.loads(archive.read(name))
        except Exception:
            continue
        releases = payload.get("releases") if isinstance(payload, dict) else None
        if not isinstance(releases, list):
            continue
        for release in releases:
            if not isinstance(release, dict):
                continue
            compact = _compact_release(name, release)
            tags = _tags(release)
            version_counts[str(compact["file_version"])] += 1
            for tag in tags or ("<none>",):
                tag_counts[tag] += 1
            tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
            if str(tender.get("mainProcurementCategory") or "").lower() != "works":
                continue
            all_works.append(compact)
            for tag in tags or ("<none>",):
                works_tag_counts[tag] += 1
            if compact["file_version"] > 1:
                versioned_works.append(compact)
            low = {tag.lower() for tag in tags}
            if any(token in low for token in {"award", "contract", "tendercancellation", "cancellation"}):
                terminal_works.append(compact)
            if "tender" in low:
                tender_works.append(compact)

    evidence["tag_counts"] = dict(tag_counts)
    evidence["works_tag_counts"] = dict(works_tag_counts)
    evidence["version_counts"] = dict(version_counts)
    evidence["candidates"] = {
        "works_total": len(all_works),
        "versioned_works": versioned_works[:8],
        "terminal_works": terminal_works[:8],
        "tender_works": tender_works[:5],
    }
    assert all_works

    selected = []
    for group in (versioned_works, terminal_works, tender_works):
        for item in group:
            if item["notice_id"] not in {x["notice_id"] for x in selected}:
                selected.append(item)
            if len(selected) >= MAX_DETAILS:
                break
        if len(selected) >= MAX_DETAILS:
            break

    for item in selected:
        notice_id = item["notice_id"]
        detail = s.get(f"{DETAIL_BASE}/{notice_id}", params={"format": "domain"}, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=60)
        entry = {"candidate": item, "status": detail.status_code, "content_type": detail.headers.get("content-type"), "length": len(detail.content)}
        if detail.status_code == 200:
            entry["payload"] = _detail_summary(detail.json())
        human = s.get(f"{HUMAN_BASE}/{notice_id}", headers={"User-Agent": UA}, timeout=45, allow_redirects=True)
        entry["human_status"] = human.status_code
        evidence["details"].append(entry)

    raise AssertionError("GERMANY_DOE_LIFECYCLE_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
