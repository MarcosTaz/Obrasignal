from datetime import datetime, timezone

from ecuador_sercop import (
    EC_SERCOP_LICENSE,
    EC_SERCOP_PUBLICATION_POLICY,
    build_sercop_connector,
    normalize_sercop_package,
    sercop_bulk_url,
)


def _package(*, status="active", deadline="2026-08-25T18:00:00-05:00", release_date="2026-08-24T08:00:00-05:00"):
    ocid = "ocds-5wno2w-MCO-ROAD-2026-001-100"
    tender = {
        "id": "MCO-ROAD-2026-001-100",
        "title": "Rehabilitación de puente vial",
        "description": "Obras de rehabilitación y refuerzo estructural",
        "status": status,
        "procurementMethod": "open",
        "procurementMethodDetails": "Menor Cuantía",
        "mainProcurementCategory": "works",
        "tenderPeriod": {
            "startDate": "2026-08-20T08:00:00-05:00",
        },
        "value": {"amount": "425000.50", "currency": "USD"},
        "items": [
            {
                "id": "1",
                "description": "Rehabilitación de puente",
                "classification": {"scheme": "CPC", "id": "53211"},
            }
        ],
        "procuringEntity": {"id": "EC-RUC-1760000000001-100", "name": "Gobierno Autónomo Descentralizado"},
    }
    if deadline is not None:
        tender["tenderPeriod"]["endDate"] = deadline
    release = {
        "id": f"{ocid}-{release_date}-compiled",
        "ocid": ocid,
        "date": release_date,
        "tag": ["planning", "tender"],
        "buyer": {"id": "EC-RUC-1760000000001-100", "name": "Gobierno Autónomo Descentralizado"},
        "tender": tender,
        "parties": [
            {
                "id": "EC-RUC-1760000000001-100",
                "name": "Gobierno Autónomo Descentralizado",
                "roles": ["buyer", "procuringEntity"],
                "address": {
                    "streetAddress": "Av. Principal 123",
                    "locality": "Quito",
                    "region": "Pichincha",
                    "countryName": "Ecuador",
                },
                "contactPoint": {"name": "Compras Públicas", "email": "compras@example.invalid"},
            }
        ],
        "initiationType": "tender",
    }
    return {
        "uri": "https://portal.compraspublicas.gob.ec/sercop/datos_abiertos/",
        "license": EC_SERCOP_LICENSE,
        "version": "1.1",
        "releases": [release],
        "publisher": {
            "uid": "ocds-5wno2w",
            "name": "Servicio Nacional de Contratación Pública (SERCOP)",
        },
        "publishedDate": release_date,
        "publicationPolicy": EC_SERCOP_PUBLICATION_POLICY,
    }


def test_bulk_url_uses_public_all_methods_month_contract():
    assert sercop_bulk_url(2026, 8) == (
        "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/"
        "download?type=json&year=2026&month=8&method=all"
    )


def test_normalizer_emits_only_actionable_tender_and_preserves_native_cpc():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    row = normalize_sercop_package(_package(), now=now)

    assert row is not None
    assert row["source"] == "EC_SERCOP"
    assert row["country"] == "ECU"
    assert row["external_id"] == "ocds-5wno2w-MCO-ROAD-2026-001-100"
    assert row["signal_type"] == "TENDER"
    assert row["deadline"] == "2026-08-25T18:00:00-05:00"
    assert row["contract_type"] == "works"
    assert row["taxonomy"] == "CPC"
    assert row["category_code"] == "53211"
    assert row["cpv"] == ""
    assert row["value"] == "425000.50"
    assert row["currency"] == "USD"
    assert row["place"] == "Av. Principal 123 | Quito | Pichincha | Ecuador"
    assert row["buyer_contact"]["name"] == "Compras Públicas"
    assert row["license"] == EC_SERCOP_LICENSE
    assert row["publication_policy"] == EC_SERCOP_PUBLICATION_POLICY
    assert row["snapshot_published_at"] == "2026-08-24T08:00:00-05:00"
    assert row["url"].endswith("?ocid=ocds-5wno2w-MCO-ROAD-2026-001-100")


def test_active_status_is_not_enough_when_submission_deadline_has_passed():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    assert normalize_sercop_package(
        _package(status="active", deadline="2026-08-20T18:00:00-05:00"),
        now=now,
    ) is None


def test_missing_deadline_and_non_active_tender_are_rejected():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    assert normalize_sercop_package(_package(deadline=None), now=now) is None
    assert normalize_sercop_package(_package(status="complete"), now=now) is None


def test_package_license_and_publication_policy_are_preserved_when_present():
    package = _package()
    package["license"] = "https://example.test/source-license"
    package["publicationPolicy"] = "https://example.test/publication-policy"
    row = normalize_sercop_package(package, now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    assert row["license"] == "https://example.test/source-license"
    assert row["publication_policy"] == "https://example.test/publication-policy"


def test_connector_declares_ecuador_daily_rolling_snapshot_contract():
    connector = build_sercop_connector(session=object())
    assert connector.config.source == "EC_SERCOP"
    assert connector.config.timezone_name == "America/Guayaquil"
    assert connector.config.lookback_months == 2
    assert connector.config.refresh_after_local_hour == 6
    assert connector.config.max_compressed_bytes == 32 * 1024 * 1024
    assert connector.config.max_uncompressed_bytes == 192 * 1024 * 1024
