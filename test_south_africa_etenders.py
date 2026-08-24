from datetime import datetime, timezone

from ocds_adapter import OCDSWindowCursor
from south_africa_etenders import (
    ZA_ETENDERS_API,
    ZA_ETENDERS_ATTRIBUTION,
    ZA_ETENDERS_COVERAGE_NOTE,
    ZA_ETENDERS_LICENSE,
    build_za_connector,
    normalize_za_release,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout})
        if not self.payloads:
            raise AssertionError("unexpected extra request")
        return FakeResponse(self.payloads.pop(0))


def _release(*, status="active", deadline="2026-08-25T11:00:00Z"):
    return {
        "ocid": "ocds-9t57fa-166658",
        "id": "ocds-9t57fa-166658-2026-08-24",
        "date": "2026-08-24T00:00:00Z",
        "tag": ["compiled"],
        "buyer": {"name": "National Department of Public Works"},
        "tender": {
            "id": "ID3292083",
            "title": "Road rehabilitation works",
            "description": "Construction and rehabilitation works",
            "status": status,
            "category": "Construction",
            "province": "Gauteng",
            "deliveryLocation": "Pretoria",
            "specialConditions": "CIDB requirements apply",
            "mainProcurementCategory": "works",
            "procurementMethod": "open",
            "procurementMethodDetails": "Open procedure",
            "tenderPeriod": {"startDate": "2026-08-20T00:00:00Z", "endDate": deadline},
            "value": {"amount": 12000000, "currency": "ZAR"},
            "briefingSession": {"isSession": True, "compulsory": True, "date": "2026-08-22"},
            "contactPerson": {"name": "Procurement Office", "email": "public@example.invalid"},
        },
    }


def _record(release):
    return {"ocid": release["ocid"], "compiledRelease": release, "_package_uri": ZA_ETENDERS_API}


def test_normalizer_preserves_za_extensions_and_attribution():
    row = normalize_za_release(_record(_release()), now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))

    assert row is not None
    assert row["source"] == "ZA_ETENDERS"
    assert row["country"] == "ZAF"
    assert row["external_id"] == "ocds-9t57fa-166658"
    assert row["deadline"] == "2026-08-25T11:00:00Z"
    assert row["place"] == "Pretoria"
    assert row["province"] == "Gauteng"
    assert row["delivery_location"] == "Pretoria"
    assert row["source_category"] == "Construction"
    assert row["license"] == ZA_ETENDERS_LICENSE
    assert row["attribution"] == ZA_ETENDERS_ATTRIBUTION
    assert "not guaranteed" in ZA_ETENDERS_COVERAGE_NOTE
    assert row["url"].endswith("/release/ocds-9t57fa-166658")


def test_normalizer_rejects_expired_or_non_active_tender():
    now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    assert normalize_za_release(_record(_release(deadline="2026-08-24T09:59:59Z")), now=now) is None
    assert normalize_za_release(_record(_release(status="complete")), now=now) is None


def test_source_connector_uses_official_parameter_names_and_advances_completed_window():
    session = FakeSession([
        {
            "uri": ZA_ETENDERS_API,
            "version": "1.1",
            "publishedDate": "2026-08-24T10:00:00Z",
            "license": ZA_ETENDERS_LICENSE,
            "publicationPolicy": "https://data.etenders.gov.za/Home/LearnMore",
            "releases": [_release()],
            "links": {},
        }
    ])
    connector = build_za_connector(session=session)
    connector.config = type(connector.config)(
        **{**connector.config.__dict__, "initial_lookback_days": 0, "overlap_days": 0}
    )

    rows, cursor = connector.fetch_incremental(
        lambda record: normalize_za_release(record, now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)),
        now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    assert session.calls[0]["url"] == ZA_ETENDERS_API
    assert session.calls[0]["params"] == {
        "dateFrom": "2026-08-24",
        "dateTo": "2026-08-24",
        "PageNumber": "1",
        "PageSize": "500",
    }
    assert OCDSWindowCursor.decode(cursor).completed_through == "2026-08-24"


def test_source_connector_declares_no_auth_or_hydration():
    connector = build_za_connector(session=FakeSession([]))
    assert connector.config.page_param == "PageNumber"
    assert connector.config.page_size_param == "PageSize"
    assert connector.config.page_size == 500
    assert connector.config.hydrate_records is False
    assert connector.headers_provider is None
