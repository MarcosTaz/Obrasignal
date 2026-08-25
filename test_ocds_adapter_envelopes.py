"""Regression coverage for official APIs that wrap OCDS bodies in API envelopes."""
from datetime import datetime, timezone

from ocds_adapter import OCDSAPIConfig, OCDSAPIConnector, normalize_ocds_record


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
        return FakeResponse(self.payloads.pop(0))


def _release(ocid):
    return {
        "ocid": ocid,
        "id": f"{ocid}-release",
        "date": "2026-08-25T00:00:00Z",
        "tag": ["tender"],
        "buyer": {"name": "Public Buyer"},
        "tender": {
            "id": f"{ocid}-tender",
            "title": "Road works",
            "status": "active",
            "mainProcurementCategory": "works",
            "items": [{"classification": {"scheme": "UNSPSC", "id": "72141000"}}],
        },
    }


def _config():
    return OCDSAPIConfig(
        source="WRAPPED",
        country="TST",
        search_url="https://publisher.test/releases/all",
        page_size=10,
        max_pages_per_window=2,
        window_days=1,
        max_windows_per_sync=1,
        initial_lookback_days=0,
        overlap_days=0,
        record_url_template="https://publisher.test/releases?ocid={ocid}",
        hydrate_records=True,
        max_hydrations_per_window=5,
    )


def test_wrapped_content_list_is_discovery_and_wrapped_content_object_hydrates():
    ocid = "ocds-test-1"
    session = FakeSession([
        {
            "code": 200,
            "hasError": False,
            "payload": {"content": [{"ocid": ocid, "url": f"https://publisher.test/releases?ocid={ocid}"}]},
        },
        {
            "code": 200,
            "hasError": False,
            "payload": {"content": {"version": "1.1", "releases": [_release(ocid)]}},
        },
    ])
    connector = OCDSAPIConnector(_config(), params_factory=lambda start, end: {}, session=session)
    rows, cursor = connector.fetch_incremental(
        lambda record: normalize_ocds_record(
            record,
            source="WRAPPED",
            country="TST",
            require_active_tender=True,
        ),
        now=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    assert [row["external_id"] for row in rows] == [ocid]
    assert cursor == '{"completed_through":"2026-08-25"}'
    assert session.calls == [
        ("https://publisher.test/releases/all", {"page": "1", "items_per_page": "10"}),
        (f"https://publisher.test/releases?ocid={ocid}", {}),
    ]
