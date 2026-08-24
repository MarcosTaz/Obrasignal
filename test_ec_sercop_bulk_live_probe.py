"""Temporary forensic probe for the official SERCOP monthly OCDS JSON bulk export.

Delete after the download contract and package shape are frozen.
"""
from collections import Counter
from io import BytesIO
import json
import zipfile

import requests

URL = (
    "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/download"
    "?type=json&year=2026&month=08&method=all"
)
HEADERS = {
    "Accept": "application/zip, application/octet-stream, application/json",
    "User-Agent": "ObraSignal procurement connector research/0.1 (+official open-data validation)",
}


def _summary_dict(value):
    if not isinstance(value, dict):
        return {"type": type(value).__name__}
    summary = {"keys": sorted(value.keys())}
    for key in ("uri", "version", "license", "publicationPolicy", "publishedDate"):
        if key in value:
            summary[key] = value.get(key)
    releases = value.get("releases")
    if isinstance(releases, list):
        summary["release_count"] = len(releases)
        if releases and isinstance(releases[0], dict):
            summary["first_release_keys"] = sorted(releases[0].keys())
    return summary


def _release_from_entry(entry):
    if not isinstance(entry, dict):
        return None
    releases = entry.get("releases")
    if isinstance(releases, list) and releases and isinstance(releases[0], dict):
        return releases[0]
    # Some SERCOP bulk exports serialize releases directly inside the root list.
    if "ocid" in entry and "id" in entry:
        return entry
    return None


def _compact_release(release):
    if not isinstance(release, dict):
        return None
    tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
    planning = release.get("planning") if isinstance(release.get("planning"), dict) else {}
    buyer = release.get("buyer") if isinstance(release.get("buyer"), dict) else {}
    items = tender.get("items") if isinstance(tender.get("items"), list) else []
    classifications = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        classification = item.get("classification")
        if isinstance(classification, dict):
            classifications.append(classification)
        for row in item.get("additionalClassifications") or []:
            if isinstance(row, dict):
                classifications.append(row)
    return {
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
            "item_count": len(items),
            "classifications": classifications[:12],
        },
        "planning_keys": sorted(planning.keys()),
        "release_keys": sorted(release.keys()),
    }


def test_sercop_august_2026_bulk_shape_and_construction_semantics_live():
    response = requests.get(URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    payload = response.content
    diagnostics = {
        "status": response.status_code,
        "url": response.url,
        "content_type": response.headers.get("content-type"),
        "content_disposition": response.headers.get("content-disposition"),
        "content_length": len(payload),
        "zip": zipfile.is_zipfile(BytesIO(payload)),
    }
    if not diagnostics["zip"]:
        raise AssertionError(diagnostics)

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = archive.namelist()
        diagnostics["entries"] = names[:20]
        diagnostics["entry_count"] = len(names)
        json_names = [name for name in names if name.lower().endswith(".json")]
        diagnostics["json_count"] = len(json_names)
        if not json_names:
            raise AssertionError(diagnostics)
        with archive.open(json_names[0]) as handle:
            root = json.load(handle)

    diagnostics["json_root_type"] = type(root).__name__
    diagnostics["root_length"] = len(root) if isinstance(root, list) else None
    if isinstance(root, list):
        diagnostics["first_entry"] = _summary_dict(root[0]) if root else None
        key_shapes = Counter(
            tuple(sorted(entry.keys())) for entry in root[:500] if isinstance(entry, dict)
        )
        diagnostics["entry_key_shapes"] = [
            {"count": count, "keys": list(keys)} for keys, count in key_shapes.most_common(5)
        ]
        releases = [release for release in (_release_from_entry(entry) for entry in root) if release]
    elif isinstance(root, dict):
        diagnostics["root"] = _summary_dict(root)
        releases = root.get("releases") if isinstance(root.get("releases"), list) else []
    else:
        releases = []

    diagnostics["extractable_release_count"] = len(releases)
    tag_counts = Counter()
    tender_status_counts = Counter()
    category_counts = Counter()
    scheme_counts = Counter()
    construction = None
    for release in releases:
        if not isinstance(release, dict):
            continue
        for tag in release.get("tag") or []:
            tag_counts[str(tag)] += 1
        tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
        status = tender.get("status")
        if status:
            tender_status_counts[str(status)] += 1
        category = tender.get("mainProcurementCategory")
        if category:
            category_counts[str(category)] += 1
        items = tender.get("items") if isinstance(tender.get("items"), list) else []
        codes = []
        for item in items:
            if not isinstance(item, dict):
                continue
            for classification in [item.get("classification"), *(item.get("additionalClassifications") or [])]:
                if not isinstance(classification, dict):
                    continue
                scheme = str(classification.get("scheme") or "")
                if scheme:
                    scheme_counts[scheme] += 1
                code = str(classification.get("id") or "")
                if code:
                    codes.append((scheme, code, classification.get("description")))
        text = " ".join(
            str(value or "")
            for value in (
                tender.get("title"),
                tender.get("description"),
                tender.get("procurementMethodDetails"),
            )
        ).lower()
        is_construction = (
            str(category or "").lower() == "works"
            or "obra" in text
            or any(code.startswith("45") for _scheme, code, _description in codes)
        )
        if construction is None and is_construction:
            construction = _compact_release(release)

    diagnostics["tag_counts"] = dict(tag_counts.most_common(12))
    diagnostics["tender_status_counts"] = dict(tender_status_counts.most_common(12))
    diagnostics["category_counts"] = dict(category_counts.most_common(12))
    diagnostics["classification_schemes"] = dict(scheme_counts.most_common(12))
    diagnostics["construction_sample"] = construction
    raise AssertionError(diagnostics)
