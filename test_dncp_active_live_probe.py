"""Temporary forensic live probe; remove after one successful CI run."""
import requests

from paraguay_dncp import DNCP_SEARCH_URL, normalize_dncp_process


def test_official_dncp_v3_active_works_filter_live():
    response = requests.get(
        DNCP_SEARCH_URL,
        params={
            "fecha_desde": "2026-07-01",
            "fecha_hasta": "2026-08-24",
            "tipo_fecha": "fecha_release",
            "tender.mainProcurementCategory": "works",
            "tender.status": "active",
            "order": "date desc",
            "page": "1",
            "items_per_page": "20",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict), payload
    records = payload.get("records")
    assert isinstance(records, list), payload.keys()
    assert records, "official DNCP active-works query returned no records"

    normalized = [normalize_dncp_process(record) for record in records]
    active = [item for item in normalized if item]
    assert active, {
        "record_count": len(records),
        "statuses": [
            ((record.get("compiledRelease") or {}).get("tender") or {}).get("status")
            for record in records
        ],
    }
    for item in active:
        assert item["source"] == "PY_DNCP"
        assert item["signal_type"] == "TENDER"
        assert item["contract_type"] == "works"
        assert item["external_id"].startswith("ocds-03ad3f-")
