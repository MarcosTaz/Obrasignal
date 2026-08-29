from datetime import date, datetime, timezone
from dataclasses import replace

from dominican_republic_dgcp import (
    DGCP_CONFIG,
    DGCP_LICENSE,
    DGCP_OCDS_DETAIL_URL_TEMPLATE,
    DGCP_OCDS_RELEASES_URL,
    dgcp_search_params,
    normalize_dgcp_process,
)
from ocds_adapter import OCDSAPIConnector
from source_registry import SOURCES, production_gate_reasons, production_ready_sources


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
        return FakeResponse(self.responses.pop(0))


def _release(*, category="works", status="active", ocid="ocds-6550wx-DO1.PCCNTR.1"):
    return {
        "ocid": ocid,
        "id": f"{ocid}-release",
        "date": "2026-08-24T14:00:00-04:00",
        "tag": ["tender"],
        "buyer": {"name": "Ministerio de Obras Públicas"},
        "tender": {
            "id": f"{ocid}-tender",
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


def _candidate(ocid):
    return {
        "ocid": ocid,
        "url": DGCP_OCDS_DETAIL_URL_TEMPLATE.format(ocid=ocid),
    }


def _discovery(candidates):
    return {
        "code": 200,
        "hasError": False,
        "payload": {"content": list(candidates)},
    }


def _detail(ocid, *, wrapped=False):
    package = {"version": "1.1", "releases": [_release(ocid=ocid)]}
    if not wrapped:
        return package
    return {
        "code": 200,
        "hasError": False,
        "payload": {"content": package},
    }


def test_config_uses_live_proven_discovery_plus_bounded_detail_hydration():
    assert DGCP_CONFIG.source == "DO_DGCP"
    assert DGCP_CONFIG.country == "DOM"
    assert DGCP_CONFIG.search_url == DGCP_OCDS_RELEASES_URL
    assert DGCP_CONFIG.page_param == "page"
    assert DGCP_CONFIG.page_size_param == "limit"
    assert DGCP_CONFIG.page_size <= 1000
    assert DGCP_CONFIG.window_days == 1
    assert DGCP_CONFIG.hydrate_records is True
    assert DGCP_CONFIG.record_url_template == DGCP_OCDS_DETAIL_URL_TEMPLATE
    assert DGCP_CONFIG.max_hydrations_per_window == 250


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


def test_connector_unwraps_discovery_envelope_then_hydrates_each_ocid():
    config = replace(
        DGCP_CONFIG,
        page_size=2,
        max_pages_per_window=3,
        initial_lookback_days=0,
        overlap_days=0,
        max_windows_per_sync=1,
        max_hydrations_per_window=10,
    )
    ocids = ["ocds-6550wx-A", "ocds-6550wx-B", "ocds-6550wx-C"]
    session = FakeSession([
        _discovery([_candidate(ocids[0]), _candidate(ocids[1])]),
        _discovery([_candidate(ocids[2])]),
        _detail(ocids[0]),
        _detail(ocids[1], wrapped=True),
        _detail(ocids[2]),
    ])
    connector = OCDSAPIConnector(config, params_factory=dgcp_search_params, session=session)
    rows, cursor = connector.fetch_incremental(
        normalize_dgcp_process,
        now=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    assert [row["external_id"] for row in rows] == ocids
    assert len(session.calls) == 5
    assert session.calls[0]["url"] == DGCP_OCDS_RELEASES_URL
    assert session.calls[0]["params"]["page"] == "1"
    assert session.calls[0]["params"]["limit"] == "2"
    assert session.calls[1]["params"]["page"] == "2"
    assert session.calls[2]["url"] == DGCP_OCDS_DETAIL_URL_TEMPLATE.format(ocid=ocids[0])
    assert session.calls[2]["params"] == {}
    assert cursor == '{"completed_through":"2026-08-25"}'


def test_registry_reflects_live_lifecycle_but_remains_runtime_gated():
    source = SOURCES["DO_DGCP"]
    assert source["source_id"] == "do_dgcp_open_data"
    assert source["status"] == "planned"
    assert source["machine_access"] == "VERIFIED"
    assert source["legal_reuse"] == "GREEN"
    assert source["adapter"] == "OCDSReleasePackageConnector+DGCPPACCConnector"
    assert set(source["capabilities"]) == {
        "incremental_sync", "detail", "plans", "awards", "contracts", "lifecycle"
    }
    assert source["signal_types"] == (
        "PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"
    )
    assert production_gate_reasons("DO_DGCP") == ("runtime_not_enabled",)
    assert "DO_DGCP" not in production_ready_sources()
