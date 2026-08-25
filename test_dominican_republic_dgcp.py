from datetime import date, datetime, timezone

from dominican_republic_dgcp import (
    DGCP_CONFIG,
    DGCP_LICENSE,
    DGCP_OCDS_RELEASES_URL,
    dgcp_connector,
    dgcp_search_params,
    normalize_dgcp_process,
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
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({
            "url": url,
            "params": dict(params),
            "headers": dict(headers),
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def _release(*, category="works", status="active", ocid="ocds-6550wx-DO1.PCCNTR.1"):
    return {
        "ocid": ocid,
        "id": f"{ocid}-release",
        "date": "2026-08-24T14:00:00-04:00",
        "tag": ["tender"],
        "buyer": {"name": "Ministerio de Obras Públicas"},
        "tender": {
            "id": "DO1.PCCNTR.1",
            "title": "Construcción de infraestructura vial",
            "description": "Obras civiles",
            "status": status,
            "mainProcurementCategory": category,
            "procurementMethod": "open",
            "tenderPeriod": {"endDate": "2026-09-15T10:00:00-04:00"},
            "value": {"amount": 125000000, "currency": "DOP"},
            "items": [
                {
                    "classification": {
                        "scheme": "UNSPSC",
                        "id": "72141000",
                    }
                }
            ],
        },
    }


def test_config_uses_official_bounded_page_date_ocds_endpoint():
    assert DGCP_CONFIG.source == "DO_DGCP"
    assert DGCP_CONFIG.country == "DOM"
    assert DGCP_CONFIG.search_url == DGCP_OCDS_RELEASES_URL
    assert DGCP_CONFIG.page_param == "page"
    assert DGCP_CONFIG.page_size_param == "limit"
    assert DGCP_CONFIG.page_size <= 1000
    assert DGCP_CONFIG.window_days == 1


def test_search_params_only_use_documented_date_filters():
    params = dgcp_search_params(date(2026, 8, 24), date(2026, 8, 25))
    assert params == {
        "start_date": "2026-08-24",
        "end_date": "2026-08-25",
    }


def test_normalizer_admits_only_active_publisher_native_works():
    record = {"ocid": "ocds-6550wx-DO1.PCCNTR.1", "compiledRelease": _release()}
    item = normalize_dgcp_process(record)
    assert item is not None
    assert item["source"] == "DO_DGCP"
    assert item["country"] == "DOM"
    assert item["external_id"] == "ocds-6550wx-DO1.PCCNTR.1"
    assert item["taxonomy"] == "UNSPSC"
    assert item["category_code"] == "72141000"
    assert item["cpv"] == ""
    assert item["contract_type"] == "works"
    assert item["currency"] == "DOP"
    assert item["license"] == DGCP_LICENSE

    goods = {"ocid": "goods", "compiledRelease": _release(category="goods", ocid="goods")}
    complete = {"ocid": "complete", "compiledRelease": _release(status="complete", ocid="complete")}
    assert normalize_dgcp_process(goods) is None
    assert normalize_dgcp_process(complete) is None


def test_connector_uses_limit_pagination_and_stops_on_short_page():
    first = [_release(ocid=f"ocds-6550wx-{index}") for index in range(2)]
    # page_size is overridden in-place for this isolated transport test through
    # a dataclass replacement to avoid hundreds of fixture rows.
    from dataclasses import replace
    from ocds_adapter import OCDSAPIConnector

    config = replace(
        DGCP_CONFIG,
        page_size=2,
        max_pages_per_window=3,
        initial_lookback_days=0,
        overlap_days=0,
        max_windows_per_sync=1,
    )
    session = FakeSession([
        FakeResponse({"version": "1.1", "releases": first}),
        FakeResponse({"version": "1.1", "releases": [_release(ocid="ocds-6550wx-final")]}),
    ])
    connector = OCDSAPIConnector(config, params_factory=dgcp_search_params, session=session)
    rows, cursor = connector.fetch_incremental(
        normalize_dgcp_process,
        now=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    assert len(rows) == 3
    assert len(session.calls) == 2
    assert session.calls[0]["params"]["page"] == "1"
    assert session.calls[0]["params"]["limit"] == "2"
    assert session.calls[1]["params"]["page"] == "2"
    assert cursor == '{"completed_through":"2026-08-25"}'
