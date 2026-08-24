"""Temporary timezone diagnostic for Find a Tender updated-range filters; delete after freeze."""
import requests

from uk_find_tender import FTS_HEADERS, FTS_RELEASE_URL


def _ids(updated_from, updated_to):
    response = requests.get(
        FTS_RELEASE_URL,
        params={"updatedFrom": updated_from, "updatedTo": updated_to, "limit": "100"},
        headers=FTS_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    releases = payload.get("releases") if isinstance(payload, dict) else []
    return {
        "url": response.url,
        "ids": [row.get("id") for row in releases if isinstance(row, dict)],
        "dates": [row.get("date") for row in releases if isinstance(row, dict)],
        "count": len(releases) if isinstance(releases, list) else None,
    }


def test_find_tender_updated_range_timezone_contract_live():
    variants = {
        "naive_utc_clock": _ids("2026-08-24T10:05:00", "2026-08-24T10:20:00"),
        "naive_bst_clock": _ids("2026-08-24T11:05:00", "2026-08-24T11:20:00"),
        "explicit_z": _ids("2026-08-24T10:05:00Z", "2026-08-24T10:20:00Z"),
        "explicit_bst": _ids("2026-08-24T11:05:00+01:00", "2026-08-24T11:20:00+01:00"),
    }
    diagnostics = {
        key: {
            "contains_080242": "080242-2026" in value["ids"],
            **value,
        }
        for key, value in variants.items()
    }
    raise AssertionError(diagnostics)
