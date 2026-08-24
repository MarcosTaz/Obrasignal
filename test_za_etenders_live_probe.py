"""Temporary forensic probe for South Africa eTenders OCDS API; delete after contract freeze."""
from datetime import date

import requests

URL = "https://ocds-api.etenders.gov.za/api/OCDSReleases"


def _summary(value):
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(value.keys())}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first": _summary(value[0]) if value else None,
        }
    return value


def test_za_etenders_live_release_package_contract():
    response = requests.get(
        URL,
        params={
            "PageNumber": 1,
            "PageSize": 2,
            "dateFrom": "2026-08-23",
            "dateTo": "2026-08-24",
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
        },
        timeout=30,
    )
    response.raise_for_status()
    package = response.json()
    assert isinstance(package, dict), type(package)
    releases = package.get("releases")
    assert isinstance(releases, list), sorted(package.keys())
    first = releases[0] if releases else {}
    tender = first.get("tender") if isinstance(first, dict) and isinstance(first.get("tender"), dict) else {}
    diagnostics = {
        "status": response.status_code,
        "package_keys": sorted(package.keys()),
        "publishedDate": package.get("publishedDate"),
        "license": package.get("license"),
        "publicationPolicy": package.get("publicationPolicy"),
        "links": package.get("links"),
        "release_count": len(releases),
        "release_keys": sorted(first.keys()) if isinstance(first, dict) else [],
        "release_ocid": first.get("ocid") if isinstance(first, dict) else None,
        "release_id": first.get("id") if isinstance(first, dict) else None,
        "release_date": first.get("date") if isinstance(first, dict) else None,
        "release_tag": first.get("tag") if isinstance(first, dict) else None,
        "tender_keys": sorted(tender.keys()),
        "tender_status": tender.get("status"),
        "tender_title": tender.get("title"),
        "tender_deadline": (tender.get("tenderPeriod") or {}).get("endDate") if isinstance(tender.get("tenderPeriod"), dict) else None,
        "tender_classification": _summary(tender.get("classification")),
        "first_item": _summary((tender.get("items") or [None])[0]) if isinstance(tender.get("items"), list) and tender.get("items") else None,
    }
    raise AssertionError(diagnostics)
