from datetime import datetime, timezone

from ecuador_sercop import normalize_sercop_record


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _record(*, status="active", deadline="2026-09-01T15:00:00-05:00", category="works"):
    return {
        "ocid": "ocds-5wno2w-LICO-TEST-001",
        "_package_license": "https://creativecommons.org/licenses/by/3.0/ec/",
        "_package_publication_policy": "https://official.example/policy.pdf",
        "_package_published_date": "2026-08-24T06:00:00-05:00",
        "_package_version": "1.1",
        "releases": [{
            "id": "LICO-TEST-001-compiled",
            "ocid": "ocds-5wno2w-LICO-TEST-001",
            "date": "2026-08-24T06:00:00-05:00",
            "tag": ["planning", "tender"],
            "buyer": {"name": "Municipio de Prueba"},
            "tender": {
                "id": "LICO-TEST-001",
                "title": "LICO-TEST-001",
                "description": "CONSTRUCCION DE CENTRO COMUNITARIO",
                "status": status,
                "procurementMethod": "open",
                "procurementMethodDetails": "Licitación",
                "mainProcurementCategory": category,
                "value": {"amount": 125000, "currency": "USD"},
                "tenderPeriod": {
                    "startDate": "2026-08-20T08:00:00-05:00",
                    "endDate": deadline,
                },
                "items": [{
                    "classification": {
                        "scheme": "CPC",
                        "id": "54121.00.1",
                        "description": "SERVICIOS GENERALES DE CONSTRUCCION",
                    }
                }],
            },
        }],
    }


def test_active_future_works_becomes_actionable_cpc_opportunity():
    item = normalize_sercop_record(_record(), now=NOW)
    assert item["source"] == "EC_SERCOP"
    assert item["external_id"] == "ocds-5wno2w-LICO-TEST-001"
    assert item["is_actionable"] is True
    assert item["lifecycle_status"] == "active"
    assert item["contract_type"] == "works"
    assert item["taxonomy"] == "CPC"
    assert item["category_code"] == "54121.00.1"
    assert item["cpv"] == ""
    assert item["currency"] == "USD"
    assert item["title"] == "CONSTRUCCION DE CENTRO COMUNITARIO"
    assert item["publication_date"] == "2026-08-20"
    assert item["url"].endswith("/ocds/ocds-5wno2w-LICO-TEST-001")
    assert "_lifecycle_only" not in item


def test_active_but_expired_works_is_tombstone_not_legacy_opportunity():
    item = normalize_sercop_record(_record(deadline="2026-08-14T08:00:00-05:00"), now=NOW)
    assert item["is_actionable"] is False
    assert item["lifecycle_status"] == "deadline_expired"
    assert item["_lifecycle_only"] is True
    assert item["cpv"] == ""


def test_non_active_works_is_lifecycle_only():
    item = normalize_sercop_record(_record(status="complete"), now=NOW)
    assert item["is_actionable"] is False
    assert item["lifecycle_status"] == "complete"
    assert item["_lifecycle_only"] is True


def test_missing_deadline_never_becomes_actionable():
    item = normalize_sercop_record(_record(deadline=None), now=NOW)
    assert item["is_actionable"] is False
    assert item["lifecycle_status"] == "deadline_missing"


def test_non_works_is_not_emitted_even_if_text_mentions_construction():
    item = normalize_sercop_record(_record(category="services"), now=NOW)
    assert item is None
