from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import pytest

from ocds_bulk_adapter import (
    OCDSMonthlyBulkConfig,
    OCDSMonthlyBulkConnector,
    OCDSMonthlyBulkCursor,
    record_from_payload,
)


class Response:
    def __init__(self, *, content=b"", payload=None, status=200):
        self.content = content
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class Session:
    def __init__(self, bulk_by_url, records):
        self.bulk_by_url = bulk_by_url
        self.records = records
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params or {}))
        if params and "ocid" in params:
            return Response(payload=self.records[params["ocid"]])
        return Response(content=self.bulk_by_url[url])


def _zip(packages):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("releases.json", json.dumps(packages))
    return buf.getvalue()


def _package(ocid, category="works"):
    return {
        "uri": "https://official.example/data",
        "license": "https://example.test/license",
        "releases": [{
            "id": f"{ocid}-compiled",
            "ocid": ocid,
            "date": "2026-08-20T12:00:00-05:00",
            "tender": {"id": ocid, "mainProcurementCategory": category},
        }],
    }


def test_record_parser_supports_documented_record_package_and_live_release_package():
    documented = {
        "records": [{"ocid": "ocds-a", "releases": [{"ocid": "ocds-a", "id": "r1"}]}]
    }
    observed = {
        "uri": "https://official.example",
        "license": "https://example.test/license",
        "version": "1.1",
        "releases": [{"ocid": "ocds-b", "id": "r2"}],
    }
    assert record_from_payload(documented, "ocds-a")["ocid"] == "ocds-a"
    normalized = record_from_payload(observed, "ocds-b")
    assert normalized["ocid"] == "ocds-b"
    assert normalized["_package_license"] == "https://example.test/license"
    assert normalized["_package_version"] == "1.1"


def test_monthly_bulk_discovers_only_selected_ocids_dedupes_and_hydrates():
    template = "https://official.example/download?year={year}&month={month}"
    july_url = template.format(year=2026, month="07")
    august_url = template.format(year=2026, month="08")
    bulk = {
        july_url: _zip([_package("ocds-work"), _package("ocds-goods", "goods")]),
        august_url: _zip([_package("ocds-work"), _package("ocds-work-2")]),
    }
    records = {
        "ocds-work": {"releases": [{"ocid": "ocds-work", "id": "r1", "tender": {"id": "t1"}}]},
        "ocds-work-2": {"releases": [{"ocid": "ocds-work-2", "id": "r2", "tender": {"id": "t2"}}]},
    }
    session = Session(bulk, records)
    config = OCDSMonthlyBulkConfig(
        source="TEST",
        country="TST",
        bulk_url_template=template,
        record_url="https://official.example/api/record",
        overlap_months=1,
    )
    connector = OCDSMonthlyBulkConnector(
        config,
        candidate_selector=lambda package, release: release["tender"].get("mainProcurementCategory") == "works",
        normalizer=lambda record, now=None: {"external_id": record["ocid"], "source": "TEST"},
        session=session,
    )
    rows, cursor = connector.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))

    assert [row["external_id"] for row in rows] == ["ocds-work", "ocds-work-2"]
    record_calls = [params["ocid"] for _url, params in session.calls if "ocid" in params]
    assert record_calls == ["ocds-work", "ocds-work-2"]
    decoded = OCDSMonthlyBulkCursor.decode(cursor)
    assert decoded.observed_through == "2026-08-24"
    assert decoded.periods == ("2026-07", "2026-08")
    assert decoded.tracked_ocids == ()


def test_actionable_cursor_ocid_is_rehydrated_even_when_absent_from_recent_bulk():
    template = "https://official.example/download?year={year}&month={month}"
    september_url = template.format(year=2026, month="09")
    records = {
        "ocds-old-open": {
            "releases": [{"ocid": "ocds-old-open", "id": "r-old", "tender": {"id": "t-old"}}]
        }
    }
    watermark = OCDSMonthlyBulkCursor(
        observed_through="2026-08-31",
        periods=("2026-08",),
        tracked_ocids=("ocds-old-open",),
    ).encode()

    open_session = Session({september_url: _zip([])}, records)
    config = OCDSMonthlyBulkConfig(
        source="TEST",
        country="TST",
        bulk_url_template=template,
        record_url="https://official.example/api/record",
        overlap_months=0,
    )
    open_connector = OCDSMonthlyBulkConnector(
        config,
        candidate_selector=lambda *_: True,
        normalizer=lambda record, now=None: {
            "source": "TEST",
            "external_id": record["ocid"],
            "ocid": record["ocid"],
            "is_actionable": True,
        },
        session=open_session,
    )
    rows, next_cursor = open_connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )
    assert [row["external_id"] for row in rows] == ["ocds-old-open"]
    assert [params["ocid"] for _url, params in open_session.calls if "ocid" in params] == ["ocds-old-open"]
    assert OCDSMonthlyBulkCursor.decode(next_cursor).tracked_ocids == ("ocds-old-open",)

    closed_session = Session({september_url: _zip([])}, records)
    closed_connector = OCDSMonthlyBulkConnector(
        config,
        candidate_selector=lambda *_: True,
        normalizer=lambda record, now=None: {
            "source": "TEST",
            "external_id": record["ocid"],
            "ocid": record["ocid"],
            "is_actionable": False,
            "_lifecycle_only": True,
        },
        session=closed_session,
    )
    rows, closed_cursor = closed_connector.fetch_incremental(
        watermark=next_cursor,
        now=datetime(2026, 9, 6, tzinfo=timezone.utc),
    )
    assert rows[0]["_lifecycle_only"] is True
    assert OCDSMonthlyBulkCursor.decode(closed_cursor).tracked_ocids == ()


def test_legacy_cursor_without_tracked_ocids_remains_decodable():
    cursor = OCDSMonthlyBulkCursor.decode(
        '{"observed_through":"2026-08-24","periods":["2026-08"]}'
    )
    assert cursor is not None
    assert cursor.tracked_ocids == ()


def test_non_zip_bulk_fails_without_returning_cursor():
    template = "https://official.example/download?year={year}&month={month}"
    session = Session({template.format(year=2026, month="08"): b"not-a-zip"}, {})
    config = OCDSMonthlyBulkConfig(
        source="TEST",
        country="TST",
        bulk_url_template=template,
        record_url="https://official.example/api/record",
        overlap_months=0,
    )
    connector = OCDSMonthlyBulkConnector(config, candidate_selector=lambda *_: True, normalizer=lambda *_args, **_kwargs: None, session=session)
    with pytest.raises(RuntimeError, match="not a ZIP"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))


def test_hydration_hard_limit_refuses_incomplete_sync_window():
    template = "https://official.example/download?year={year}&month={month}"
    url = template.format(year=2026, month="08")
    session = Session({url: _zip([_package("ocds-1"), _package("ocds-2")])}, {})
    config = OCDSMonthlyBulkConfig(
        source="TEST",
        country="TST",
        bulk_url_template=template,
        record_url="https://official.example/api/record",
        overlap_months=0,
        max_hydrations_per_sync=1,
    )
    connector = OCDSMonthlyBulkConnector(config, candidate_selector=lambda *_: True, normalizer=lambda *_args, **_kwargs: None, session=session)
    with pytest.raises(RuntimeError, match="cursor not advanced"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))
