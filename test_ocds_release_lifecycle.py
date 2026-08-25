from datetime import datetime, timezone

import pytest

from ocds_adapter import OCDSAPIConfig
from ocds_release_lifecycle import (
    OCDSReleasePackageConnector,
    merge_nonempty_mapping,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append((url, dict(params)))
        if not self.payloads:
            raise AssertionError("unexpected request")
        return FakeResponse(self.payloads.pop(0))


def config():
    return OCDSAPIConfig(
        source="TEST",
        country="TST",
        search_url="https://example.test/search",
        page_size=10,
        max_pages_per_window=2,
        max_windows_per_sync=1,
        initial_lookback_days=0,
        overlap_days=0,
        record_url_template="https://example.test/detail?ocid={ocid}",
        hydrate_records=True,
        max_hydrations_per_window=5,
    )


def test_release_package_hydration_preserves_all_requested_ocid_releases():
    ocid = "ocds-x-1"
    releases = [
        {"ocid": ocid, "id": "r1", "date": "2026-08-24T10:00:00Z", "tender": {"status": "active"}},
        {"ocid": ocid, "id": "r2", "date": "2026-08-24T11:00:00Z", "awards": [{"id": "a1"}]},
    ]
    session = FakeSession([
        {"records": [{"ocid": ocid}], "pagination": {"total_pages": 1}},
        {"version": "1.1", "releases": releases},
    ])
    connector = OCDSReleasePackageConnector(
        config(), params_factory=lambda start, end: {}, session=session
    )
    batch = connector._fetch_window(
        datetime(2026, 8, 24, tzinfo=timezone.utc).date(),
        datetime(2026, 8, 24, tzinfo=timezone.utc).date(),
    )
    assert len(batch) == 1
    assert batch[0]["ocid"] == ocid
    assert [release["id"] for release in batch[0]["releases"]] == ["r1", "r2"]
    assert len(session.calls) == 2


def test_multi_signal_fetch_flattens_one_hydration_without_duplicate_requests():
    ocid = "ocds-x-2"
    session = FakeSession([
        {"records": [{"ocid": ocid}], "pagination": {"total_pages": 1}},
        {"releases": [{"ocid": ocid, "id": "r1", "date": "2026-08-24T10:00:00Z"}]},
    ])
    connector = OCDSReleasePackageConnector(
        config(), params_factory=lambda start, end: {}, session=session
    )
    rows, cursor = connector.fetch_incremental_many(
        lambda record: [
            {"external_id": record["ocid"], "signal_type": "TENDER"},
            {"external_id": record["ocid"] + ":contract:c1", "signal_type": "CONTRACT"},
        ],
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert [row["signal_type"] for row in rows] == ["TENDER", "CONTRACT"]
    assert len(session.calls) == 2
    assert cursor == '{"completed_through":"2026-08-24"}'


def test_recursive_nonempty_merge_preserves_nested_partial_fields():
    base = {
        "id": "c1",
        "period": {"startDate": "2026-09-01", "endDate": "2027-01-01"},
        "value": {"amount": 100, "currency": "DOP"},
    }
    patch = {
        "id": "c1",
        "period": {"endDate": "2027-02-01"},
        "value": {"amount": 110},
        "title": "Updated contract",
    }
    merged = merge_nonempty_mapping(base, patch)
    assert merged["period"] == {
        "startDate": "2026-09-01",
        "endDate": "2027-02-01",
    }
    assert merged["value"] == {"amount": 110, "currency": "DOP"}
    assert merged["title"] == "Updated contract"
    # Helper must not mutate caller-owned input.
    assert base["period"]["endDate"] == "2027-01-01"


def test_multi_signal_normalizer_fails_closed_on_malformed_output():
    connector = OCDSReleasePackageConnector(
        config(), params_factory=lambda start, end: {}, session=FakeSession([])
    )
    with pytest.raises(RuntimeError, match="non-mapping"):
        connector._normalized_many([{"external_id": "x"}, "bad"])
    with pytest.raises(RuntimeError, match="mapping/list/tuple/None"):
        connector._normalized_many("bad")
