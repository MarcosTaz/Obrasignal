"""TEMPORARY Germany DÖE untagged-Works lifecycle probe. Delete before merge."""
from __future__ import annotations

import io
import json
import re
import zipfile

import requests

EXPORT_URL = "https://oeffentlichevergabe.de/api/notice-exports"
DETAIL_BASE = "https://oeffentlichevergabe.de/api/notices"
PUB_DAY = "2026-08-21"
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 3000
MAX_DETAILS = 10
UA = "ObraSignal Germany DÖE forensic probe/3.0"


def _download(session):
    response = session.get(
        EXPORT_URL,
        params={"pubDay": PUB_DAY, "format": "ocds.zip"},
        headers={"User-Agent": UA, "Accept": "*/*"},
        timeout=90,
        stream=True,
    )
    chunks, total = [], 0
    for chunk in response.iter_content(1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_BYTES:
            raise RuntimeError("DÖE probe ZIP exceeded hard limit")
        chunks.append(chunk)
    return response, b"".join(chunks)


def _identity(name):
    base = re.sub(r"\.json$", "", name.rsplit("/", 1)[-1], flags=re.I)
    match = re.match(r"^(.+?)-(\d+)$", base)
    return (match.group(1), int(match.group(2))) if match else (base, 0)


def _simple(value):
    if isinstance(value, dict):
        return {str(k): _simple(v) for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        return [_simple(v) for v in value[:15]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _summary(payload):
    lots = payload.get("lots") if isinstance(payload, dict) and isinstance(payload.get("lots"), list) else []
    return {
        "noticeIdentifier": payload.get("noticeIdentifier"),
        "originalNoticeIdentifier": payload.get("originalNoticeIdentifier"),
        "procedureIdentifier": payload.get("procedureIdentifier"),
        "noticeVersion": payload.get("noticeVersion"),
        "noticeType": _simple(payload.get("noticeType")),
        "noticeSubType": _simple(payload.get("noticeSubType")),
        "publicationDate": payload.get("publicationDate"),
        "changeDate": payload.get("changeDate"),
        "purpose": _simple(payload.get("purpose")),
        "procedure": _simple(payload.get("procedure")),
        "lots": [
            {
                "id": lot.get("id"),
                "classification": _simple(lot.get("classification")),
                "submissionTerms": _simple(lot.get("submissionTerms")),
            }
            for lot in lots[:8] if isinstance(lot, dict)
        ],
    }


def test_germany_doe_untagged_works_live():
    s = requests.Session()
    response, blob = _download(s)
    assert response.status_code == 200 and blob[:4] == b"PK\x03\x04"
    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = [n for n in archive.namelist() if n.lower().endswith(".json")]
    assert names and len(names) <= MAX_FILES

    candidates = []
    for name in names:
        try:
            package = json.loads(archive.read(name))
        except Exception:
            continue
        releases = package.get("releases") if isinstance(package, dict) else None
        if not isinstance(releases, list):
            continue
        for release in releases:
            if not isinstance(release, dict):
                continue
            tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
            tags = release.get("tag") if isinstance(release.get("tag"), list) else ([] if not release.get("tag") else [release.get("tag")])
            if str(tender.get("mainProcurementCategory") or "").lower() != "works" or tags:
                continue
            notice_id, version = _identity(name)
            candidates.append({
                "notice_id": notice_id,
                "file_version": version,
                "ocid": release.get("ocid"),
                "release_id": release.get("id"),
                "release_date": release.get("date"),
                "tender_id": tender.get("id"),
                "title": tender.get("title"),
                "lot_ids": [lot.get("id") for lot in tender.get("lots", []) if isinstance(lot, dict)][:8],
            })

    evidence = {"candidate_count": len(candidates), "candidates": candidates[:20], "details": []}
    assert candidates
    for candidate in candidates[:MAX_DETAILS]:
        r = s.get(
            f"{DETAIL_BASE}/{candidate['notice_id']}",
            params={"format": "domain"},
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=60,
        )
        item = {"candidate": candidate, "status": r.status_code, "content_type": r.headers.get("content-type")}
        if r.status_code == 200:
            item["payload"] = _summary(r.json())
        else:
            item["prefix"] = r.text[:1000]
        evidence["details"].append(item)

    raise AssertionError("GERMANY_DOE_UNTAGGED_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
