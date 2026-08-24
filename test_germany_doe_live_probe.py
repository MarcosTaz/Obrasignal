"""TEMPORARY Germany DÖE Open Data contract probe. Delete before merge.

The source is the federal Bekanntmachungsservice Open Data API. This probe is
bounded, uses no credentials, and intentionally fails after printing evidence.
"""
from __future__ import annotations

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
MAX_DETAIL = 4
UA = "ObraSignal Germany DÖE forensic probe/1.0"


def _download_bounded(session, url, *, params=None):
    response = session.get(url, params=params, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=90, stream=True)
    chunks = []
    total = 0
    for chunk in response.iter_content(1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_BYTES:
            raise RuntimeError(f"DÖE probe exceeded {MAX_BYTES} bytes")
        chunks.append(chunk)
    return response, b"".join(chunks)


def _compact_release(release):
    tender = release.get("tender") if isinstance(release, dict) else None
    tender = tender if isinstance(tender, dict) else {}
    return {
        "ocid": release.get("ocid"),
        "id": release.get("id"),
        "date": release.get("date"),
        "tag": release.get("tag"),
        "tender_id": tender.get("id"),
        "title": tender.get("title"),
        "status": tender.get("status"),
        "mainProcurementCategory": tender.get("mainProcurementCategory"),
        "classification": tender.get("classification"),
        "items": tender.get("items")[:2] if isinstance(tender.get("items"), list) else tender.get("items"),
        "lots": tender.get("lots")[:3] if isinstance(tender.get("lots"), list) else tender.get("lots"),
        "tenderPeriod": tender.get("tenderPeriod"),
        "documents_count": len(tender.get("documents") or []) if isinstance(tender.get("documents"), list) else None,
    }


def _notice_id_from_name(name):
    base = name.rsplit("/", 1)[-1]
    base = re.sub(r"\.(json|xml)$", "", base, flags=re.I)
    # The publisher names files <noticeId>-<version>.json; keep UUID-like notice
    # id intact and strip only a final numeric version when present.
    match = re.match(r"^(.+?)-(\d+)$", base)
    return match.group(1) if match else base


def _detail_summary(payload):
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    lots = payload.get("lots") if isinstance(payload.get("lots"), list) else []
    lot_rows = []
    for lot in lots[:8]:
        if not isinstance(lot, dict):
            continue
        terms = lot.get("submissionTerms") if isinstance(lot.get("submissionTerms"), dict) else {}
        lot_rows.append({
            "id": lot.get("id"),
            "title": lot.get("title"),
            "status": lot.get("status"),
            "mainProcurementCategory": lot.get("mainProcurementCategory"),
            "cpv": lot.get("classification") or lot.get("cpvCodes"),
            "deadlineReceiptTenders": terms.get("deadlineReceiptTenders"),
            "deadlineReceiptRequests": terms.get("deadlineReceiptRequests"),
            "submissionUrl": terms.get("submissionUrl"),
        })
    return {
        "keys": sorted(payload.keys()),
        "id": payload.get("id") or payload.get("noticeId"),
        "noticeVersion": payload.get("noticeVersion"),
        "noticeType": payload.get("noticeType") or payload.get("noticeTypeCode"),
        "publicationDate": payload.get("publicationDate"),
        "procedure": payload.get("procedure") if isinstance(payload.get("procedure"), (str, int, float, bool, type(None))) else None,
        "lots": lot_rows,
        "lot_count": len(lots),
    }


def test_germany_doe_open_data_live():
    s = requests.Session()
    evidence = {"export": {}, "samples": [], "works": [], "details": []}

    response, blob = _download_bounded(s, EXPORT_URL, params={"pubDay": PUB_DAY, "format": "ocds.zip"})
    evidence["export"] = {
        "status": response.status_code,
        "url": response.url,
        "content_type": response.headers.get("content-type"),
        "content_length": response.headers.get("content-length"),
        "received": len(blob),
        "magic": blob[:8].hex(),
    }
    assert response.status_code == 200
    assert blob[:4] == b"PK\x03\x04"

    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = [name for name in archive.namelist() if not name.endswith("/")]
    assert names and len(names) <= MAX_FILES
    evidence["export"]["file_count"] = len(names)
    evidence["export"]["first_names"] = names[:12]

    works_candidates = []
    for name in names:
        if not name.lower().endswith(".json"):
            continue
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
            compact = _compact_release(release)
            if len(evidence["samples"]) < 8:
                evidence["samples"].append({"file": name, **compact})
            tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
            if str(tender.get("mainProcurementCategory") or "").lower() == "works":
                item = {"file": name, "notice_id_guess": _notice_id_from_name(name), **compact}
                works_candidates.append(item)
                if len(evidence["works"]) < 8:
                    evidence["works"].append(item)
        if len(works_candidates) >= MAX_DETAIL:
            break

    for item in works_candidates[:MAX_DETAIL]:
        notice_id = item["notice_id_guess"]
        detail = s.get(
            f"{DETAIL_BASE}/{notice_id}",
            params={"format": "domain"},
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=60,
            allow_redirects=True,
        )
        entry = {
            "notice_id": notice_id,
            "status": detail.status_code,
            "url": detail.url,
            "content_type": detail.headers.get("content-type"),
            "length": len(detail.content),
        }
        if detail.status_code == 200:
            try:
                entry["payload"] = _detail_summary(detail.json())
            except Exception:
                entry["prefix"] = detail.text[:2500]
        human = s.get(f"{HUMAN_BASE}/{notice_id}", headers={"User-Agent": UA}, timeout=45, allow_redirects=True)
        entry["human"] = {"status": human.status_code, "url": human.url, "content_type": human.headers.get("content-type")}
        evidence["details"].append(entry)

    assert works_candidates, "no Works release found in bounded daily export"
    raise AssertionError("GERMANY_DOE_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
