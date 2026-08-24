"""TEMPORARY Germany DOE OpenData semantic probe. Delete before merge."""
from __future__ import annotations

from io import BytesIO
import json
import re
import zipfile

import requests

BASE = "https://oeffentlichevergabe.de"
SPEC = f"{BASE}/documentation/api/opendata"
EXPORTS = f"{BASE}/api/notice-exports"
UA = "ObraSignal Germany DOE forensic probe/2.0"
EFORMS = "application/vnd.bekanntmachungsservice.eforms.zip+zip"
OCDS2 = "application/vnd.bekanntmachungsservice.ocds2.zip+zip"
DAY = "2026-08-23"
MAX_ZIP = 32 * 1024 * 1024


def _download(session, accept):
    response = session.get(EXPORTS, params={"pubDay": DAY}, headers={"Accept": accept}, timeout=90, stream=True)
    data = bytearray()
    try:
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_ZIP:
                raise AssertionError(f"export exceeds bounded probe limit {MAX_ZIP}")
    finally:
        response.close()
    return response, bytes(data)


def _xml_evidence(data):
    zf = zipfile.ZipFile(BytesIO(data))
    names = zf.namelist()
    samples, works = [], []
    for name in names[:400]:
        raw = zf.read(name)
        text = raw.decode("utf-8", errors="replace")
        root = re.search(r"<([A-Za-z0-9_:.-]+)(?:\s|>)", text)
        notice_id = re.search(r"<(?:cbc:)?ID(?:\s[^>]*)?>([^<]+)</", text)
        folder = re.search(r"<(?:cbc:)?ContractFolderID(?:\s[^>]*)?>([^<]+)</", text)
        issue_date = re.search(r"<(?:cbc:)?IssueDate(?:\s[^>]*)?>([^<]+)</", text)
        proc_type = re.findall(r"<(?:cbc:)?ProcurementTypeCode(?:\s[^>]*)?>([^<]+)</", text)
        deadlines = re.findall(r"<(?:cbc:)?EndDate(?:\s[^>]*)?>([^<]+)</", text)
        cpvs = re.findall(r"<(?:cbc:)?ItemClassificationCode[^>]*listName=[\"']cpv[\"'][^>]*>([^<]+)</", text, flags=re.I)
        row = {
            "name": name,
            "root": root.group(1) if root else "",
            "notice_id": notice_id.group(1).strip() if notice_id else "",
            "contract_folder_id": folder.group(1).strip() if folder else "",
            "issue_date": issue_date.group(1).strip() if issue_date else "",
            "procurement_types": proc_type[:8],
            "deadlines": deadlines[:8],
            "cpvs": cpvs[:12],
            "bytes": len(raw),
        }
        if len(samples) < 12:
            samples.append(row)
        if any(value.strip().lower() == "works" for value in proc_type):
            works.append(row)
            if len(works) >= 8:
                break
    return {"entry_count": len(names), "first_names": names[:25], "samples": samples, "works": works}


def _ocds_evidence(data):
    zf = zipfile.ZipFile(BytesIO(data))
    names = zf.namelist()
    docs = []
    for name in names[:30]:
        raw = zf.read(name)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            docs.append({"name": name, "bytes": len(raw), "json": False, "prefix": raw[:300].decode("utf-8", errors="replace")})
            continue
        info = {"name": name, "bytes": len(raw), "json": True, "top_keys": sorted(payload.keys())[:30] if isinstance(payload, dict) else []}
        if isinstance(payload, dict):
            releases = payload.get("releases") if isinstance(payload.get("releases"), list) else []
            info["release_count"] = len(releases)
            sample = []
            for release in releases[:5]:
                if not isinstance(release, dict):
                    continue
                tender = release.get("tender") if isinstance(release.get("tender"), dict) else {}
                sample.append({
                    "ocid": release.get("ocid"), "id": release.get("id"), "date": release.get("date"),
                    "tag": release.get("tag"), "tender_status": tender.get("status"),
                    "mainProcurementCategory": tender.get("mainProcurementCategory"),
                    "title": tender.get("title"),
                })
            info["sample_releases"] = sample
        docs.append(info)
    return {"entry_count": len(names), "first_names": names[:25], "docs": docs}


def test_germany_doe_semantics_live():
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    evidence = {}

    spec_response = session.get(SPEC, headers={"Accept": "application/json"}, timeout=45)
    spec = spec_response.json() if spec_response.status_code == 200 else {}
    operation = (((spec.get("paths") or {}).get("/api/notice-exports") or {}).get("get") or {}) if isinstance(spec, dict) else {}
    evidence["spec"] = {
        "status": spec_response.status_code,
        "openapi": spec.get("openapi") if isinstance(spec, dict) else None,
        "title": ((spec.get("info") or {}).get("title")) if isinstance(spec, dict) else None,
        "parameters": operation.get("parameters"),
        "responses": operation.get("responses"),
    }

    for label, accept, parser in (("eforms", EFORMS, _xml_evidence), ("ocds2", OCDS2, _ocds_evidence)):
        response, data = _download(session, accept)
        info = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "content_disposition": response.headers.get("content-disposition"),
            "bytes": len(data),
            "magic": data[:8].hex(),
        }
        if response.status_code == 200 and data.startswith(b"PK"):
            info["archive"] = parser(data)
        else:
            info["prefix"] = data[:5000].decode("utf-8", errors="replace")
        evidence[label] = info

    raise AssertionError("GERMANY_DOE_SEMANTIC_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:220000])
