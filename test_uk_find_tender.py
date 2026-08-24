from datetime import datetime, timezone

import pytest

from ocds_cursor_adapter import OCDSOpaqueWindowCursor
from uk_find_tender import (
    FTS_LICENSE,
    UKFindTenderConnector,
    normalize_uk_record,
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
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout})
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def _record(*, status="active", deadline="2026-09-21T12:00:00+01:00", category="works", lot_status="active"):
    return {
        "ocid": "ocds-h6vhtk-06ea4b",
        "compiledRelease": {
            "id": "compiled-current",
            "date": "2026-08-24T11:13:05+01:00",
            "tag": ["tender"],
            "buyer": {"id": "GB-PPON-PYYD-8699-BJGD", "name": "City & County of Swansea"},
            "tender": {
                "id": "CCS/26/170",
                "title": "Contract for the Execution of Environmental Facilities West Cross Phase 2",
                "description": "Environmental facilities construction works",
                "status": status,
                "mainProcurementCategory": category,
                "procurementMethod": "open",
                "procurementMethodDetails": "Below threshold - open competition",
                "value": {"amount": 1279700.73, "currency": "GBP"},
                "tenderPeriod": {"endDate": deadline},
                "lots": [
                    {
                        "id": "1",
                        "title": "1",
                        "description": "Lot 1-69 Houses",
                        "status": lot_status,
                        "value": {"amount": 830682.93, "currency": "GBP"},
                        "suitability": {"sme": True},
                    },
                    {
                        "id": "2",
                        "title": "2",
                        "description": "Lot 2- 27 Houses 10 Blocks of Flats",
                        "status": lot_status,
                        "value": {"amount": 449017.8, "currency": "GBP"},
                        "suitability": {"sme": True},
                    },
                ],
                "items": [
                    {
                        "id": "1",
                        "relatedLot": "1",
                        "additionalClassifications": [
                            {"scheme": "CPV", "id": "45233253", "description": "Surface work for footpaths"},
                            {"scheme": "CPV", "id": "45000000", "description": "Construction work"},
                        ],
                        "deliveryAddresses": [{"region": "UKL18", "country": "GB", "countryName": "United Kingdom"}],
                    },
                    {
                        "id": "2",
                        "relatedLot": "2",
                        "additionalClassifications": [
                            {"scheme": "CPV", "id": "45112700", "description": "Landscaping work"},
                            {"scheme": "CPV", "id": "45000000", "description": "Construction work"},
                        ],
                        "deliveryAddresses": [{"region": "UKL18", "country": "GB", "countryName": "United Kingdom"}],
                    },
                ],
            },
        },
        "releases": [
            {"id": "080242-2026", "date": "2026-08-24T11:13:05+01:00", "ocid": "ocds-h6vhtk-06ea4b"},
        ],
    }


def test_current_active_construction_record_emits_two_actionable_lots():
    rows = normalize_uk_record(_record(), now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc))

    assert [row["external_id"] for row in rows] == [
        "ocds-h6vhtk-06ea4b:lot:1",
        "ocds-h6vhtk-06ea4b:lot:2",
    ]
    assert rows[0]["source"] == "UK_PROCUREMENT"
    assert rows[0]["signal_type"] == "TENDER"
    assert rows[0]["is_actionable"] is True
    assert rows[0]["lifecycle_status"] == "active"
    assert rows[0]["value"] == "830682.93"
    assert rows[0]["currency"] == "GBP"
    assert rows[0]["cpv"] == "45233253"
    assert rows[0]["cpv_codes"] == ["45233253", "45000000"]
    assert rows[1]["cpv"] == "45112700"
    assert rows[0]["place"] == "UKL18 | United Kingdom | GB"
    assert rows[0]["sme_suitable"] is True
    assert rows[0]["license"] == FTS_LICENSE
    assert rows[0]["url"].endswith("/ocdsReleasePackages/080242-2026")
    assert "_lifecycle_only" not in rows[0]


def test_complete_process_emits_same_lot_ids_as_lifecycle_tombstones():
    rows = normalize_uk_record(
        _record(status="complete"),
        now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc),
    )
    assert [row["external_id"] for row in rows] == [
        "ocds-h6vhtk-06ea4b:lot:1",
        "ocds-h6vhtk-06ea4b:lot:2",
    ]
    assert all(row["is_actionable"] is False for row in rows)
    assert all(row["_lifecycle_only"] is True for row in rows)
    assert all(row["lifecycle_status"] == "complete" for row in rows)


def test_closed_lot_tombstones_only_that_lot_semantically():
    record = _record()
    record["compiledRelease"]["tender"]["lots"][1]["status"] = "complete"
    rows = normalize_uk_record(record, now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc))
    assert rows[0]["is_actionable"] is True
    assert rows[1]["is_actionable"] is False
    assert rows[1]["lifecycle_status"] == "complete"
    assert rows[1]["_lifecycle_only"] is True


def test_elapsed_deadline_is_not_sold_as_open_even_if_publisher_status_is_active():
    rows = normalize_uk_record(
        _record(deadline="2026-08-24T09:00:00Z"),
        now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc),
    )
    assert all(row["is_actionable"] is False for row in rows)
    assert all(row["lifecycle_status"] == "deadline_elapsed" for row in rows)


def test_non_construction_record_is_excluded_without_fake_cpv_mapping():
    record = _record(category="services")
    record["compiledRelease"]["tender"]["items"] = [
        {"id": "1", "relatedLot": "1", "additionalClassifications": [{"scheme": "CPV", "id": "72000000"}]},
    ]
    assert normalize_uk_record(record, now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc)) == []


def test_lot_without_source_id_fails_closed_instead_of_creating_unstable_identity():
    record = _record()
    record["compiledRelease"]["tender"]["lots"][0].pop("id")
    with pytest.raises(RuntimeError, match="lot without id"):
        normalize_uk_record(record, now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc))


def test_connector_uses_subdaily_updated_range_without_unproven_stages_filter_and_hydrates_once_per_ocid():
    release_package = {
        "releases": [
            {"ocid": "ocds-h6vhtk-06ea4b", "id": "080242-2026"},
            {"ocid": "ocds-h6vhtk-06ea4b", "id": "duplicate-same-ocid"},
        ]
    }
    record_package = {"records": [_record()]}
    session = FakeSession([FakeResponse(release_package), FakeResponse(record_package)])
    connector = UKFindTenderConnector(session=session)
    # Replace long bootstrap with one deterministic 15-minute UTC window.
    connector.transport.config = type(connector.transport.config)(
        **{
            **connector.transport.config.__dict__,
            "initial_lookback_minutes": 15,
            "max_windows_per_sync": 1,
            "overlap_minutes": 0,
        }
    )
    now = datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc)

    rows, cursor = connector.fetch_incremental(now=now)

    assert len(rows) == 2
    assert len(session.calls) == 2
    search_params = session.calls[0]["params"]
    # FTS interprets updatedFrom/updatedTo on the Europe/London clock. Internal
    # cursor state remains UTC; only the API boundary is converted to London time.
    assert search_params["updatedFrom"] == "2026-08-24T11:45:00+01:00"
    assert search_params["updatedTo"] == "2026-08-24T12:00:00+01:00"
    assert "stages" not in search_params
    assert session.calls[1]["url"].endswith("/ocdsRecordPackages/ocds-h6vhtk-06ea4b")
    assert OCDSOpaqueWindowCursor.decode(cursor).completed_through == "2026-08-24T11:00:00Z"


def test_hydration_limit_fails_closed_before_record_requests():
    releases = [{"ocid": f"ocid-{i}"} for i in range(3)]
    session = FakeSession([FakeResponse({"releases": releases})])
    connector = UKFindTenderConnector(session=session, max_hydrations_per_window=2)
    connector.transport.config = type(connector.transport.config)(
        **{
            **connector.transport.config.__dict__,
            "initial_lookback_minutes": 15,
            "max_windows_per_sync": 1,
            "overlap_minutes": 0,
        }
    )
    with pytest.raises(RuntimeError, match="above max_hydrations_per_window=2"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc))
    assert len(session.calls) == 1
