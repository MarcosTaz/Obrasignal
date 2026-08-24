from datetime import datetime, timezone

import pytest

from ocds_adapter import (
    OCDSAPIConfig,
    OCDSAPIConnector,
    OCDSWindowCursor,
    normalize_ocds_record,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout})
        if not self.pages:
            return FakeResponse({"records": [], "pagination": {"total_pages": 0}})
        return FakeResponse(self.pages.pop(0))


def _config(**overrides):
    values = dict(
        source="TEST_OCDS",
        country="TST",
        search_url="https://example.test/search",
        page_size=2,
        max_pages_per_window=3,
        window_days=1,
        max_windows_per_sync=2,
        initial_lookback_days=1,
        overlap_days=1,
    )
    values.update(overrides)
    return OCDSAPIConfig(**values)


def _params(start, end):
    return {"from": start.isoformat(), "until": end.isoformat(), "kind": "works"}


def _minimal_record(ocid, *, release_date="2026-08-23T10:00:00Z", status="active", scheme="UNSPSC"):
    return {
        "ocid": ocid,
        "compiledRelease": {
            "ocid": ocid,
            "id": f"{ocid}-release",
            "date": release_date,
            "tag": ["tender"],
            "buyer": {"name": "Road Authority"},
            "tender": {
                "id": f"{ocid}-tender",
                "title": "Bridge rehabilitation",
                "description": "Civil works",
                "status": status,
                "procurementMethod": "open",
                "mainProcurementCategory": "works",
                "tenderPeriod": {"endDate": "2026-09-10T12:00:00Z"},
                "value": {"amount": 2500000, "currency": "USD"},
                "items": [{"classification": {"scheme": scheme, "id": "72141000"}}],
            },
        },
    }


def test_cursor_roundtrip_and_date_compatibility():
    cursor = OCDSWindowCursor("2026-08-24")
    assert OCDSWindowCursor.decode(cursor.encode()) == cursor
    assert OCDSWindowCursor.decode("2026-08-24") == cursor
    assert OCDSWindowCursor.decode("not-a-date") is None


def test_incremental_fetch_completes_pages_and_date_windows_before_advancing_cursor():
    session = FakeSession([
        {"records": [_minimal_record("ocds-x-A"), _minimal_record("ocds-x-B")], "pagination": {"total_pages": 2}},
        {"records": [_minimal_record("ocds-x-C")], "pagination": {"total_pages": 2}},
        {"records": [], "pagination": {"total_pages": 0}},
    ])
    connector = OCDSAPIConnector(_config(), params_factory=_params, session=session)
    rows, cursor = connector.fetch_incremental(
        lambda record: normalize_ocds_record(record, source="TEST_OCDS", country="TST"),
        now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
    )

    assert [row["external_id"] for row in rows] == ["ocds-x-A", "ocds-x-B", "ocds-x-C"]
    assert len(session.calls) == 3
    assert session.calls[0]["params"]["from"] == "2026-08-23"
    assert session.calls[0]["params"]["page"] == "1"
    assert session.calls[1]["params"]["page"] == "2"
    assert session.calls[2]["params"]["from"] == "2026-08-24"
    assert OCDSWindowCursor.decode(cursor) == OCDSWindowCursor("2026-08-24")


def test_existing_cursor_replays_overlap_window():
    session = FakeSession([
        {"records": [], "pagination": {"total_pages": 0}},
        {"records": [], "pagination": {"total_pages": 0}},
    ])
    connector = OCDSAPIConnector(_config(), params_factory=_params, session=session)
    connector.fetch_incremental(
        lambda record: record,
        watermark=OCDSWindowCursor("2026-08-24").encode(),
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert session.calls[0]["params"]["from"] == "2026-08-23"


def test_total_pages_above_safety_limit_fails_without_returning_cursor():
    session = FakeSession([
        {"records": [_minimal_record("ocds-x-A")], "pagination": {"total_pages": 4}},
    ])
    connector = OCDSAPIConnector(_config(max_pages_per_window=3), params_factory=_params, session=session)
    with pytest.raises(RuntimeError, match="above max_pages_per_window"):
        connector.fetch_incremental(
            lambda record: record,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_release_package_is_accepted_by_common_normalizer():
    release = _minimal_record("ocds-x-R")["compiledRelease"]
    session = FakeSession([
        {"uri": "https://publisher.test/releases", "releases": [release], "pagination": {"total_pages": 1}},
    ])
    connector = OCDSAPIConnector(
        _config(page_size=10, max_windows_per_sync=1),
        params_factory=_params,
        session=session,
    )
    rows, _ = connector.fetch_incremental(
        lambda record: normalize_ocds_record(record, source="TEST_OCDS", country="TST"),
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert rows[0]["external_id"] == "ocds-x-R"
    assert rows[0]["url"] == "https://publisher.test/releases"


def test_normalizer_preserves_native_taxonomy_and_does_not_fake_cpv():
    item = normalize_ocds_record(_minimal_record("ocds-x-1"), source="X", country="TST")
    assert item["taxonomy"] == "UNSPSC"
    assert item["category_code"] == "72141000"
    assert item["cpv"] == ""
    assert item["contract_type"] == "works"
    assert item["value"] == "2500000"
    assert item["currency"] == "USD"


def test_normalizer_only_populates_cpv_when_scheme_is_actually_cpv():
    item = normalize_ocds_record(_minimal_record("ocds-x-2", scheme="CPV"), source="X", country="TST")
    assert item["taxonomy"] == "CPV"
    assert item["cpv"] == "72141000"


@pytest.mark.parametrize("status", ["planned", "complete", "cancelled", "unsuccessful", "withdrawn"])
def test_live_tender_filter_rejects_non_active_processes(status):
    item = normalize_ocds_record(
        _minimal_record(f"ocds-x-{status}", status=status),
        source="X",
        country="TST",
        require_active_tender=True,
    )
    assert item is None


def test_live_tender_filter_accepts_only_active_process():
    item = normalize_ocds_record(
        _minimal_record("ocds-x-active", status="active"),
        source="X",
        country="TST",
        require_active_tender=True,
    )
    assert item is not None
    assert item["signal_type"] == "TENDER"
