from dataclasses import replace
from datetime import datetime, timezone

from dominican_republic_dgcp import (
    DGCP_CONFIG,
    fetch_dgcp_signals,
    normalize_dgcp_lifecycle,
    normalize_dgcp_process,
    normalize_dgcp_signals,
)
from ocds_release_lifecycle import OCDSReleasePackageConnector


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


def package(*, category="works", tender_status="active"):
    ocid = "ocds-6550wx-MOPC-CCC-LPN-2026-0001"
    return {
        "ocid": ocid,
        "releases": [
            {
                "ocid": ocid,
                "id": "r1",
                "date": "2026-08-20T10:00:00-04:00",
                "tag": ["tender"],
                "buyer": {"name": "Ministerio de Obras Públicas"},
                "tender": {
                    "id": "t1",
                    "title": "Rehabilitación de carretera",
                    "description": "Obras viales",
                    "status": tender_status,
                    "mainProcurementCategory": category,
                    "tenderPeriod": {"endDate": "2026-09-30T10:00:00-04:00"},
                    "items": [{"classification": {"scheme": "UNSPSC", "id": "72141000"}}],
                    "value": {"amount": 100000000, "currency": "DOP"},
                },
            },
            {
                "ocid": ocid,
                "id": "r2",
                "date": "2026-08-22T12:00:00-04:00",
                "tag": ["award"],
                "awards": [
                    {
                        "id": "a1",
                        "date": "2026-08-22T11:00:00-04:00",
                        "status": "active",
                        "suppliers": [{"id": "RPE-10", "name": "Constructora Uno SRL"}],
                    }
                ],
            },
            {
                "ocid": ocid,
                "id": "r3",
                "date": "2026-08-23T09:00:00-04:00",
                "tag": ["contract"],
                "contracts": [
                    {
                        "id": "c1",
                        "awardID": "a1",
                        "title": "Contrato carretera",
                        "status": "active",
                        "value": {"amount": 95000000, "currency": "DOP"},
                        "period": {
                            "startDate": "2026-09-15T00:00:00-04:00",
                            "endDate": "2027-03-15T00:00:00-04:00",
                        },
                    }
                ],
            },
            {
                "ocid": ocid,
                "id": "r4",
                "date": "2026-08-24T09:00:00-04:00",
                "tag": ["contractUpdate"],
                "contracts": [{"id": "c1", "status": "active"}],
            },
        ],
    }


def test_tender_uses_latest_release_that_contains_tender_not_latest_partial_release():
    item = normalize_dgcp_process(package())
    assert item is not None
    assert item["signal_type"] == "TENDER"
    assert item["title"] == "Rehabilitación de carretera"
    assert item["taxonomy"] == "UNSPSC"


def test_lifecycle_emits_canonical_award_and_contract_with_stable_identity():
    rows = normalize_dgcp_lifecycle(package())
    assert [row["signal_type"] for row in rows] == ["AWARD", "CONTRACT"]

    award, contract = rows
    assert award["external_id"].endswith(":award:a1")
    assert award["supplier"] == "Constructora Uno SRL"
    assert award["source_status"] == "active"
    assert award["contract_type"] == "works"

    assert contract["external_id"].endswith(":contract:c1")
    assert contract["value"] == "95000000"
    assert contract["currency"] == "DOP"
    assert contract["target_date"] == "2026-09-15T00:00:00-04:00"
    assert contract["contract_end_date"] == "2027-03-15T00:00:00-04:00"
    assert contract["supplier"] == "Constructora Uno SRL"
    # The later partial update must not erase value/period/title.
    assert contract["title"] == "Contrato carretera"


def test_non_works_package_emits_no_dgcp_signals():
    assert normalize_dgcp_process(package(category="goods")) is None
    assert normalize_dgcp_lifecycle(package(category="goods")) == []
    assert normalize_dgcp_signals(package(category="goods")) == []


def test_completed_tender_can_still_emit_lifecycle_without_becoming_live_tender():
    record = package(tender_status="complete")
    rows = normalize_dgcp_signals(record)
    assert [row["signal_type"] for row in rows] == ["AWARD", "CONTRACT"]


def test_fetch_dgcp_signals_uses_one_detail_hydration_for_three_signal_types():
    ocid = package()["ocid"]
    discovery = {
        "code": 200,
        "hasError": False,
        "payload": {"content": [{"ocid": ocid, "url": "https://example.test/detail"}]},
    }
    detail = {"code": 200, "hasError": False, "payload": {"content": package()}}
    session = FakeSession([discovery, detail])
    config = replace(
        DGCP_CONFIG,
        initial_lookback_days=0,
        overlap_days=0,
        max_windows_per_sync=1,
        page_size=10,
    )
    connector = OCDSReleasePackageConnector(
        config,
        params_factory=lambda start, end: {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        session=session,
    )
    rows, cursor = fetch_dgcp_signals(
        connector=connector,
        now=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )
    assert {row["signal_type"] for row in rows} == {"TENDER", "AWARD", "CONTRACT"}
    assert len(session.calls) == 2
    assert cursor == '{"completed_through":"2026-08-25"}'
