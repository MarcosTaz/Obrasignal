"""Temporary live proof of the current Find a Tender record-package shape; delete after freeze."""
import requests

URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages/ocds-h6vhtk-06ea4b"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement connector research/0.1 (+official open-data validation)",
}


def test_current_find_tender_record_package_shape_live():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("records") if isinstance(payload, dict) else None
    record = records[0] if isinstance(records, list) and records else {}
    compiled = record.get("compiledRelease") if isinstance(record, dict) else None
    tender = compiled.get("tender") if isinstance(compiled, dict) and isinstance(compiled.get("tender"), dict) else {}
    diagnostics = {
        "status": response.status_code,
        "root_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "license": payload.get("license") if isinstance(payload, dict) else None,
        "record_count": len(records) if isinstance(records, list) else None,
        "record_keys": sorted(record.keys()) if isinstance(record, dict) else [],
        "ocid": record.get("ocid") if isinstance(record, dict) else None,
        "compiled": isinstance(compiled, dict),
        "compiled_release_id": compiled.get("id") if isinstance(compiled, dict) else None,
        "compiled_date": compiled.get("date") if isinstance(compiled, dict) else None,
        "tender_status": tender.get("status"),
        "main_category": tender.get("mainProcurementCategory"),
        "title": tender.get("title"),
        "deadline": (tender.get("tenderPeriod") or {}).get("endDate") if isinstance(tender.get("tenderPeriod"), dict) else None,
        "lot_count": len(tender.get("lots") or []) if isinstance(tender.get("lots"), list) else None,
        "lots": tender.get("lots"),
        "item_count": len(tender.get("items") or []) if isinstance(tender.get("items"), list) else None,
        "items": tender.get("items"),
        "release_count": len(record.get("releases") or []) if isinstance(record.get("releases"), list) else None,
    }
    raise AssertionError(diagnostics)
