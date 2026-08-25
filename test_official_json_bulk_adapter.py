from datetime import datetime, timezone

import pytest

from official_json_bulk_adapter import (
    DailyBulkCursor,
    OfficialJSONBulkAdapter,
    OfficialJSONBulkConfig,
)


class FakeResponse:
    def __init__(self, payload=None, *, status=200, content=None):
        self.payload = payload
        self.status_code = status
        self.content = content if content is not None else (b"[]" if payload == [] else b"{json}")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


def _url(day):
    return f"https://example.test/{day.isoformat()}.json"


def _config(**overrides):
    values = dict(
        source="TEST_BULK",
        country="TST",
        url_factory=_url,
        initial_lookback_days=0,
        overlap_days=0,
        max_days_per_sync=2,
        publication_lag_days=1,
        timeout=30,
    )
    values.update(overrides)
    return OfficialJSONBulkConfig(**values)


def _normalizer(notice, *, publication_day, now=None):
    return {"external_id": notice["id"], "publication_date": publication_day.isoformat()}


def test_daily_cursor_round_trip():
    cursor = DailyBulkCursor("2026-08-23")
    assert DailyBulkCursor.decode(cursor.encode()) == cursor
    assert DailyBulkCursor.decode("2026-08-23") == cursor
    assert DailyBulkCursor.decode("bad") is None


def test_publication_lag_processes_only_last_expected_file():
    session = FakeSession([FakeResponse([{"id": "a"}])])
    adapter = OfficialJSONBulkAdapter(_config(), normalizer=_normalizer, session=session)
    rows, cursor = adapter.fetch_incremental(now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))

    assert rows == [{"external_id": "a", "publication_date": "2026-08-23"}]
    assert session.calls[0]["url"].endswith("2026-08-23.json")
    assert DailyBulkCursor.decode(cursor) == DailyBulkCursor("2026-08-23")


def test_zero_overlap_starts_on_first_unseen_publication_day():
    session = FakeSession([FakeResponse([])])
    adapter = OfficialJSONBulkAdapter(_config(overlap_days=0), normalizer=_normalizer, session=session)
    _, cursor = adapter.fetch_incremental(
        watermark=DailyBulkCursor("2026-08-22").encode(),
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert session.calls[0]["url"].endswith("2026-08-23.json")
    assert DailyBulkCursor.decode(cursor) == DailyBulkCursor("2026-08-23")


def test_one_day_overlap_replays_exact_last_completed_day():
    session = FakeSession([FakeResponse([]), FakeResponse([])])
    adapter = OfficialJSONBulkAdapter(
        _config(overlap_days=1, max_days_per_sync=2),
        normalizer=_normalizer,
        session=session,
    )
    _, cursor = adapter.fetch_incremental(
        watermark=DailyBulkCursor("2026-08-22").encode(),
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert [call["url"].rsplit("/", 1)[-1] for call in session.calls] == ["2026-08-22.json", "2026-08-23.json"]
    assert DailyBulkCursor.decode(cursor) == DailyBulkCursor("2026-08-23")


def test_empty_json_list_is_a_healthy_completed_day():
    session = FakeSession([FakeResponse([], content=b"[]")])
    adapter = OfficialJSONBulkAdapter(_config(), normalizer=_normalizer, session=session)
    rows, cursor = adapter.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))
    assert rows == []
    assert DailyBulkCursor.decode(cursor) == DailyBulkCursor("2026-08-23")


def test_missing_expected_file_fails_closed():
    session = FakeSession([FakeResponse(None, status=404, content=b"not found")])
    adapter = OfficialJSONBulkAdapter(_config(), normalizer=_normalizer, session=session)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))


def test_empty_body_and_invalid_shape_fail_closed():
    empty_session = FakeSession([FakeResponse(None, content=b"")])
    adapter = OfficialJSONBulkAdapter(_config(), normalizer=_normalizer, session=empty_session)
    with pytest.raises(RuntimeError, match="was empty; cursor not advanced"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))

    shape_session = FakeSession([FakeResponse({"unexpected": "object"})])
    adapter = OfficialJSONBulkAdapter(_config(), normalizer=_normalizer, session=shape_session)
    with pytest.raises(RuntimeError, match="not a supported notice list"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))


def test_normalizer_exception_prevents_completed_cursor_return():
    session = FakeSession([FakeResponse([{"id": "a"}])])

    def broken(*args, **kwargs):
        raise RuntimeError("normalizer failed")

    adapter = OfficialJSONBulkAdapter(_config(), normalizer=broken, session=session)
    with pytest.raises(RuntimeError, match="normalizer failed"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))
