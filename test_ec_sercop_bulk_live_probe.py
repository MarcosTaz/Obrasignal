"""Temporary forensic probe for the official SERCOP monthly OCDS JSON bulk export.

Delete after bulk discovery + record hydration contracts are frozen.
"""
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import requests

BULK_URL = (
    "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/download"
    "?type=json&year=2026&month=08&method=all"
)
RECORD_URL = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/record"
HEADERS = {
    "Accept": "application/zip, application/octet-stream, application/json",
    "User-Agent": "ObraSignal procurement connector research/0.1 (+official open-data validation)",
}
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _dt(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _release_from_entry(entry):
    if not isinstance(entry, dict):
        return None
    releases = entry.get("releases")
    if isinstance(releases, list) and releases and isinstance(releases[0], dict):
        return releases[0]
    return None


def _classifications(tender):
    out = []
    for item in tender.get("items") or []:
        if not isinstance(item, dict):
            continue
        candidates = [item.get("classification"), *(item.get("additionalClassifications") or [])]
        for row in candidates:
            if isinstance(row, dict):
                out.append({
                    "scheme": row.get("scheme"),
                    "id": row.get("id"),
                    "description": row.get("description"),
                    "uri": row.get("uri"),
                })
    return out


def _compact_release(release, package=None):
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    buyer = release.get("buyer") if isinstance(release.get("buyer"), dict) else {}
    documents = tender.get("documents") if isinstance(tender.get("documents"), list) else []
    return {
        "package_publishedDate": package.get("publishedDate") if isinstance(package, dict) else None,
        "package_license": package.get("license") if isinstance(package, dict) else None,
        "id": release.get("id"),
        "ocid": release.get("ocid"),
        "date": release.get("date"),
        "tag": release.get("tag"),
        "buyer": {"id": buyer.get("id"), "name": buyer.get("name")},
        "tender": {
            "id": tender.get("id"),
            "title": tender.get("title"),
            "description": tender.get("description"),
            "status": tender.get("status"),
            "procurementMethod": tender.get("procurementMethod"),
            "procurementMethodDetails": tender.get("procurementMethodDetails"),
            "mainProcurementCategory": tender.get("mainProcurementCategory"),
            "value": tender.get("value"),
            "tenderPeriod": tender.get("tenderPeriod"),
            "contractPeriod": tender.get("contractPeriod"),
            "classification_count": len(_classifications(tender)),
            "classifications": _classifications(tender)[:8],
            "document_count": len(documents),
            "documents": [
                {"id": row.get("id"), "documentType": row.get("documentType"), "url": row.get("url")}
                for row in documents[:5] if isinstance(row, dict)
            ],
        },
    }


def _record_summary(payload, requested_ocid):
    records = payload.get("records") if isinstance(payload, dict) else None
    record = None
    if isinstance(records, list):
        for candidate in records:
            if isinstance(candidate, dict) and candidate.get("ocid") == requested_ocid:
                record = candidate
                break
    if not isinstance(record, dict):
        return {
            "root_keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
            "record_count": len(records) if isinstance(records, list) else None,
            "matched": False,
        }
    releases = [row for row in (record.get("releases") or []) if isinstance(row, dict)]
    release_states = []
    for release in releases[-8:]:
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        release_states.append({
            "id": release.get("id"),
            "date": release.get("date"),
            "tag": release.get("tag"),
            "tender_status": tender.get("status"),
            "deadline": (tender.get("tenderPeriod") or {}).get("endDate") if isinstance(tender.get("tenderPeriod"), dict) else None,
            "category": tender.get("mainProcurementCategory"),
        })
    return {
        "root_keys": sorted(payload.keys()),
        "license": payload.get("license"),
        "version": payload.get("version"),
        "record_count": len(records),
        "matched": True,
        "record_keys": sorted(record.keys()),
        "release_count": len(releases),
        "compiledRelease": isinstance(record.get("compiledRelease"), dict),
        "versionedRelease": isinstance(record.get("versionedRelease"), dict),
        "release_states": release_states,
    }


def test_sercop_bulk_discovery_and_record_current_state_contract_live():
    response = requests.get(BULK_URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    payload = response.content
    diagnostics = {
        "bulk_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "content_disposition": response.headers.get("content-disposition"),
        "content_length": len(payload),
        "etag": response.headers.get("etag"),
        "last_modified": response.headers.get("last-modified"),
        "zip": zipfile.is_zipfile(BytesIO(payload)),
    }
    if not diagnostics["zip"]:
        raise AssertionError(diagnostics)

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".json")]
        diagnostics["entries"] = names
        if not names:
            raise AssertionError(diagnostics)
        with archive.open(names[0]) as handle:
            root = json.load(handle)

    if not isinstance(root, list):
        diagnostics["root_type"] = type(root).__name__
        raise AssertionError(diagnostics)

    diagnostics["package_count"] = len(root)
    package_dates = [_dt(entry.get("publishedDate")) for entry in root if isinstance(entry, dict)]
    package_dates = [value for value in package_dates if value]
    diagnostics["package_published_min"] = min(package_dates).isoformat() if package_dates else None
    diagnostics["package_published_max"] = max(package_dates).isoformat() if package_dates else None

    pairs = []
    for package in root:
        release = _release_from_entry(package)
        if release:
            pairs.append((package, release))
    diagnostics["release_count"] = len(pairs)

    tag_counts = Counter()
    status_counts = Counter()
    category_counts = Counter()
    scheme_counts = Counter()
    works_total = 0
    works_active_future = []
    works_active_expired = []
    works_complete = []
    cross_month_updates = []

    for package, release in pairs:
        for tag in release.get("tag") or []:
            tag_counts[str(tag)] += 1
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        status = str(tender.get("status") or "")
        category = str(tender.get("mainProcurementCategory") or "")
        if status:
            status_counts[status] += 1
        if category:
            category_counts[category] += 1
        for row in _classifications(tender):
            if row.get("scheme"):
                scheme_counts[str(row["scheme"])] += 1

        release_date = _dt(release.get("date"))
        tender_period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
        start = _dt(tender_period.get("startDate"))
        deadline = _dt(tender_period.get("endDate"))
        if release_date and start and release_date.month == 8 and start < datetime(2026, 8, 1, tzinfo=timezone.utc):
            if len(cross_month_updates) < 5:
                cross_month_updates.append(_compact_release(release, package))

        if category.lower() != "works":
            continue
        works_total += 1
        compact = _compact_release(release, package)
        if status.lower() == "active" and deadline and deadline > NOW:
            if len(works_active_future) < 5:
                works_active_future.append(compact)
        elif status.lower() == "active":
            if len(works_active_expired) < 5:
                works_active_expired.append(compact)
        elif status.lower() == "complete":
            if len(works_complete) < 3:
                works_complete.append(compact)

    diagnostics["tag_counts"] = dict(tag_counts.most_common(10))
    diagnostics["status_counts"] = dict(status_counts.most_common(10))
    diagnostics["category_counts"] = dict(category_counts.most_common(10))
    diagnostics["scheme_counts"] = dict(scheme_counts.most_common(10))
    diagnostics["works_total"] = works_total
    diagnostics["works_active_future_count_sampled"] = len(works_active_future)
    diagnostics["works_active_future"] = works_active_future
    diagnostics["works_active_expired"] = works_active_expired
    diagnostics["works_complete"] = works_complete
    diagnostics["cross_month_updates"] = cross_month_updates

    target = works_active_future[0] if works_active_future else (works_active_expired[0] if works_active_expired else None)
    if target and target.get("ocid"):
        record_response = requests.get(
            RECORD_URL,
            params={"ocid": target["ocid"]},
            headers={"Accept": "application/json", "User-Agent": HEADERS["User-Agent"]},
            timeout=45,
        )
        diagnostics["record_http_status"] = record_response.status_code
        record_response.raise_for_status()
        diagnostics["record"] = _record_summary(record_response.json(), target["ocid"])

    raise AssertionError(diagnostics)
