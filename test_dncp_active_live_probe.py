"""Temporary forensic live probe; remove after DNCP hydration is understood."""
import time

import requests

from paraguay_dncp import DNCP_API_ROOT, DNCP_SEARCH_URL, normalize_dncp_process


def test_official_dncp_v3_search_then_record_hydration_live():
    search = requests.get(
        DNCP_SEARCH_URL,
        params={
            "fecha_desde": "2026-07-01",
            "fecha_hasta": "2026-08-24",
            "tipo_fecha": "fecha_release",
            "tender.mainProcurementCategory": "works",
            "tender.status": "active",
            "order": "date desc",
            "page": "1",
            "items_per_page": "3",
        },
        timeout=30,
    )
    search.raise_for_status()
    payload = search.json()
    candidates = payload.get("records") if isinstance(payload, dict) else None
    assert isinstance(candidates, list), payload
    assert candidates, "official DNCP works search returned no records"

    hydrated = []
    for candidate in candidates[:3]:
        ocid = candidate.get("ocid")
        assert ocid, candidate
        time.sleep(0.35)
        response = requests.get(
            f"{DNCP_API_ROOT}/ocds/record/{ocid}",
            timeout=30,
        )
        response.raise_for_status()
        package = response.json()
        assert isinstance(package, dict), type(package)
        records = package.get("records")
        assert isinstance(records, list) and records, package.keys()
        matching = [record for record in records if record.get("ocid") == ocid]
        hydrated.append(matching[0] if matching else records[0])

    statuses = [
        ((record.get("compiledRelease") or {}).get("tender") or {}).get("status")
        for record in hydrated
    ]
    assert statuses and all(status == "active" for status in statuses), statuses

    normalized = [normalize_dncp_process(record) for record in hydrated]
    assert all(normalized), statuses
    for item in normalized:
        assert item["source"] == "PY_DNCP"
        assert item["signal_type"] == "TENDER"
        assert item["contract_type"] == "works"
        assert item["external_id"].startswith("ocds-03ad3f-")
