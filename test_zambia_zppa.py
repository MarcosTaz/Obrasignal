import gzip
import io
import json
from datetime import datetime, timezone

import pytest

from ocds_jsonl_snapshot import OCDSJSONLGzipConfig, OCDSJSONLGzipSnapshotConnector
from zambia_zppa import build_zm_connector, fetch_zm_tenders, normalize_zm_release


NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def _compiled(*, ocid="ocds-23g63a01-123", category="works", status="active", deadline="2026-09-30T12:00:00Z"):
    return {
        "ocid": ocid,
        "id": f"{ocid}-1",
        "date": "2026-08-20T10:00:00Z",
        "tag": ["tender"],
        "buyer": {"name": "Road Development Agency"},
        "tender": {
            "id": "RDA/W/001/2026",
            "title": "Rehabilitation of trunk road",
            "description": "Road rehabilitation and drainage works",
            "status": status,
            "mainProcurementCategory": category,
            "procurementMethod": "open",
            "tenderPeriod": {"endDate": deadline},
            "value": {"amount": 12000000, "currency": "ZMW"},
            "items": [
                {
                    "classification": {
                        "scheme": "UNSPSC",
                        "id": "72141000",
                        "description": "Highway and road construction services",
                    }
                }
            ],
        },
    }


def _record(**kwargs):
    compiled = _compiled(**kwargs)
    return {"ocid": compiled["ocid"], "compiledRelease": compiled}


def _gz_jsonl(*payloads):
    raw = b"".join(json.dumps(row).encode("utf-8") + b"\n" for row in payloads)
    return gzip.compress(raw)


class _Response:
    def __init__(self, body, *, status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1024 * 1024):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]


class _Session:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_normalize_zm_release_emits_only_active_future_public_works():
    item = normalize_zm_release(_record(), now=NOW)

    assert item["source"] == "ZM_ZPPA"
    assert item["country"] == "ZMB"
    assert item["external_id"] == "ocds-23g63a01-123"
    assert item["signal_type"] == "TENDER"
    assert item["buyer"] == "Road Development Agency"
    assert item["contract_type"] == "works"
    assert item["construction_filter"] == "OCDS tender.mainProcurementCategory=works"
    assert item["license"].endswith("/by/4.0/")
    assert "Zambia Public Procurement Authority" in item["attribution"]
    assert "complete real-time national coverage" in item["coverage_note"]


def test_normalize_zm_release_rejects_non_works_expired_and_inactive_tenders():
    assert normalize_zm_release(_record(category="goods"), now=NOW) is None
    assert normalize_zm_release(_record(deadline="2026-08-24T23:59:59Z"), now=NOW) is None
    assert normalize_zm_release(_record(status="complete"), now=NOW) is None


def test_jsonl_snapshot_parses_compiled_releases_and_is_stable_across_reingestion():
    body = _gz_jsonl(_compiled(), _compiled(ocid="ocds-23g63a01-456", category="goods"))
    session = _Session(_Response(body, headers={"Content-Length": str(len(body))}))
    connector = build_zm_connector(session=session)

    rows1, cursor1 = fetch_zm_tenders(now=NOW, connector=connector)
    rows2, cursor2 = fetch_zm_tenders(watermark=cursor1, now=NOW, connector=connector)

    assert [row["external_id"] for row in rows1] == ["ocds-23g63a01-123"]
    assert rows2 == rows1
    assert cursor1 == cursor2 == '{"snapshot_year":2026}'
    assert session.calls[0][0].endswith("name=2026.jsonl.gz")
    assert session.calls[0][1]["stream"] is True


def test_snapshot_accepts_already_wrapped_record_shape():
    body = _gz_jsonl(_record())
    session = _Session(_Response(body))
    connector = build_zm_connector(session=session)

    rows, _ = fetch_zm_tenders(now=NOW, connector=connector)

    assert len(rows) == 1
    assert rows[0]["ocid"] == "ocds-23g63a01-123"


def test_snapshot_failure_is_not_silently_converted_to_zero_opportunities():
    session = _Session(_Response(b"not-gzip"))
    connector = build_zm_connector(session=session)

    with pytest.raises(RuntimeError, match="valid gzip"):
        fetch_zm_tenders(now=NOW, connector=connector)


def test_snapshot_rejects_invalid_json_and_empty_valid_gzip():
    config = OCDSJSONLGzipConfig(
        source="TEST",
        country="ZMB",
        url_template="https://example.invalid/{year}.jsonl.gz",
    )

    invalid = OCDSJSONLGzipSnapshotConnector(config, session=_Session(_Response(gzip.compress(b"{broken}\n"))))
    with pytest.raises(RuntimeError, match="invalid OCDS JSONL"):
        invalid.fetch_snapshot(lambda row: row, now=NOW)

    empty = OCDSJSONLGzipSnapshotConnector(config, session=_Session(_Response(gzip.compress(b"\n\n"))))
    with pytest.raises(RuntimeError, match="contained no JSON records"):
        empty.fetch_snapshot(lambda row: row, now=NOW)


def test_snapshot_enforces_compressed_size_limit_before_parsing():
    body = _gz_jsonl(_compiled())
    config = OCDSJSONLGzipConfig(
        source="TEST",
        country="ZMB",
        url_template="https://example.invalid/{year}.jsonl.gz",
        max_compressed_bytes=max(1, len(body) - 1),
    )
    session = _Session(_Response(body, headers={"Content-Length": str(len(body))}))
    connector = OCDSJSONLGzipSnapshotConnector(config, session=session)

    with pytest.raises(RuntimeError, match="compressed size limit"):
        connector.fetch_snapshot(lambda row: row, now=NOW)
