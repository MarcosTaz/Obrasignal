from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import pytest

from official_zip_json_snapshot_adapter import (
    OfficialZipJSONSnapshotAdapter,
    RollingSnapshotConfig,
    RollingSnapshotCursor,
)


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.body = bytes(body)
        self.status_code = status
        self.headers = {"content-length": str(len(self.body)), **(headers or {})}
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=65536):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index:index + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, timeout, stream):
        self.calls.append({"url": url, "headers": dict(headers), "timeout": timeout, "stream": stream})
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


def _zip(rows, name="snapshot.json"):
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, json.dumps(rows))
    return output.getvalue()


def _config(**overrides):
    values = dict(
        source="TEST_SNAPSHOT",
        timezone_name="America/Guayaquil",
        lookback_months=2,
        refresh_after_local_hour=6,
        timeout=30,
        max_compressed_bytes=1024 * 1024,
        max_uncompressed_bytes=4 * 1024 * 1024,
        max_zip_entries=2,
    )
    values.update(overrides)
    return RollingSnapshotConfig(**values)


def _normalizer(unit, *, now=None):
    if unit.get("drop"):
        return None
    return {
        "source": "TEST_SNAPSHOT",
        "external_id": unit["id"],
        "source_updated_at": unit.get("updated", ""),
        "title": unit.get("title", ""),
    }


def _url(year, month):
    return f"https://official.test/{year}/{month:02d}.zip"


def test_cursor_roundtrip_and_legacy_date_compatibility():
    cursor = RollingSnapshotCursor("2026-08-24", "2026-08-24T12:00:00Z")
    assert RollingSnapshotCursor.decode(cursor.encode()) == cursor
    assert RollingSnapshotCursor.decode("2026-08-24") == RollingSnapshotCursor("2026-08-24", None)
    assert RollingSnapshotCursor.decode("not-a-date") is None


def test_post_refresh_observation_fetches_current_and_previous_month_once():
    session = FakeSession([
        FakeResponse(_zip([{"id": "current", "updated": "2026-08-24T10:00:00Z"}])),
        FakeResponse(_zip([{"id": "previous", "updated": "2026-07-30T10:00:00Z"}])),
    ])
    connector = OfficialZipJSONSnapshotAdapter(_config(), url_factory=_url, normalizer=_normalizer, session=session)

    rows, cursor = connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))

    assert [row["external_id"] for row in rows] == ["current", "previous"]
    assert [call["url"] for call in session.calls] == [
        "https://official.test/2026/08.zip",
        "https://official.test/2026/07.zip",
    ]
    assert all(call["stream"] is True for call in session.calls)
    assert RollingSnapshotCursor.decode(cursor).last_observed_local_date == "2026-08-24"


def test_same_local_day_cursor_suppresses_network_fetch():
    session = FakeSession([])
    connector = OfficialZipJSONSnapshotAdapter(_config(), url_factory=_url, normalizer=_normalizer, session=session)
    watermark = RollingSnapshotCursor("2026-08-24", "2026-08-24T12:00:00Z").encode()

    rows, cursor = connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc),
    )

    assert rows == []
    assert cursor == watermark
    assert session.calls == []


def test_before_refresh_hour_yesterday_cursor_waits_without_network():
    session = FakeSession([])
    connector = OfficialZipJSONSnapshotAdapter(_config(), url_factory=_url, normalizer=_normalizer, session=session)
    watermark = RollingSnapshotCursor("2026-08-23", "2026-08-23T12:00:00Z").encode()

    rows, cursor = connector.fetch_incremental(
        watermark=watermark,
        # 10:00 UTC = 05:00 America/Guayaquil.
        now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
    )

    assert rows == []
    assert cursor == watermark
    assert session.calls == []


def test_early_bootstrap_fetches_but_leaves_cursor_on_previous_local_day():
    session = FakeSession([FakeResponse(_zip([])), FakeResponse(_zip([]))])
    connector = OfficialZipJSONSnapshotAdapter(_config(), url_factory=_url, normalizer=_normalizer, session=session)

    rows, cursor = connector.fetch_incremental(now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))

    assert rows == []
    assert len(session.calls) == 2
    assert RollingSnapshotCursor.decode(cursor).last_observed_local_date == "2026-08-23"


def test_month_window_crosses_year_boundary_correctly():
    session = FakeSession([FakeResponse(_zip([])), FakeResponse(_zip([]))])
    connector = OfficialZipJSONSnapshotAdapter(_config(), url_factory=_url, normalizer=_normalizer, session=session)

    connector.fetch_incremental(now=datetime(2027, 1, 10, 12, 0, tzinfo=timezone.utc))

    assert [call["url"] for call in session.calls] == [
        "https://official.test/2027/01.zip",
        "https://official.test/2026/12.zip",
    ]


def test_duplicate_external_id_prefers_newer_source_update_across_snapshots():
    session = FakeSession([
        FakeResponse(_zip([{"id": "same", "updated": "2026-08-20T10:00:00Z", "title": "new"}])),
        FakeResponse(_zip([{"id": "same", "updated": "2026-07-20T10:00:00Z", "title": "old"}])),
    ])
    connector = OfficialZipJSONSnapshotAdapter(_config(), url_factory=_url, normalizer=_normalizer, session=session)

    rows, _ = connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))

    assert len(rows) == 1
    assert rows[0]["title"] == "new"


def test_declared_compressed_size_above_limit_fails_before_streaming():
    response = FakeResponse(_zip([]), headers={"content-length": "999999"})
    session = FakeSession([response])
    connector = OfficialZipJSONSnapshotAdapter(
        _config(max_compressed_bytes=100),
        url_factory=_url,
        normalizer=_normalizer,
        session=session,
    )

    with pytest.raises(RuntimeError, match="declared compressed bytes"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    assert response.closed is True


def test_streamed_body_above_limit_aborts_and_does_not_return_cursor():
    body = _zip([{"id": "x", "padding": "x" * 10000}])
    response = FakeResponse(body, headers={"content-length": "invalid"})
    session = FakeSession([response])
    connector = OfficialZipJSONSnapshotAdapter(
        _config(max_compressed_bytes=50),
        url_factory=_url,
        normalizer=_normalizer,
        session=session,
    )

    with pytest.raises(RuntimeError, match="download aborted"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    assert response.closed is True


def test_zip_member_path_traversal_is_rejected():
    session = FakeSession([FakeResponse(_zip([], name="../escape.json"))])
    connector = OfficialZipJSONSnapshotAdapter(
        _config(lookback_months=1),
        url_factory=_url,
        normalizer=_normalizer,
        session=session,
    )
    with pytest.raises(RuntimeError, match="unsafe member path"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))


def test_non_list_json_root_fails_closed():
    body = BytesIO()
    with zipfile.ZipFile(body, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("snapshot.json", json.dumps({"records": []}))
    session = FakeSession([FakeResponse(body.getvalue())])
    connector = OfficialZipJSONSnapshotAdapter(
        _config(lookback_months=1),
        url_factory=_url,
        normalizer=_normalizer,
        session=session,
    )
    with pytest.raises(RuntimeError, match="JSON root must be a list"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))


def test_normalizer_exception_aborts_entire_observation_without_cursor():
    session = FakeSession([FakeResponse(_zip([{"id": "x"}]))])

    def broken(unit, *, now=None):
        raise RuntimeError("normalization failed")

    connector = OfficialZipJSONSnapshotAdapter(
        _config(lookback_months=1),
        url_factory=_url,
        normalizer=broken,
        session=session,
    )
    with pytest.raises(RuntimeError, match="normalization failed"):
        connector.fetch_incremental(now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
