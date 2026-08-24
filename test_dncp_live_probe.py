"""Temporary forensic live probe; remove after one successful CI run."""
import requests

from ocds_adapter import normalize_ocds_record
from paraguay_dncp import DNCP_SEARCH_URL


def test_official_dncp_v3_works_search_live():
    response = requests.get(
        DNCP_SEARCH_URL,
        params={
            "fecha_desde": "2026-08-01",
            "fecha_hasta": "2026-08-24",
            "tipo_fecha": "fecha_release",
            "tender.mainProcurementCategory": "works",
            "order": "date desc",
            "page": "1",
            "items_per_page": "10",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict), payload
    assert isinstance(payload.get("records"), list), payload.keys()
    assert payload["records"], "official DNCP v3 works query returned no records"
    assert isinstance(payload.get("pagination"), dict), payload.keys()
    for record in payload["records"]:
        assert record.get("ocid"), record
        item = normalize_ocds_record(record, source="PY_DNCP", country="PRY")
        assert item is not None, record
        assert item["external_id"].startswith("ocds-03ad3f-")
