from datetime import datetime, timezone

import pytest

from ocds_cursor_adapter import (
    OCDSOpaqueCursorAdapter,
    OCDSOpaqueCursorConfig,
    OCDSOpaqueWindowCursor,
    _cursor_stamp,
    _datetime,
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
        self.calls.append((url, dict(params), dict(headers), timeout))
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def _config(**overrides):
    values = dict(
        source="UK_PROCUREMENT",
        country="GBR",
        search_url="https://example.gov/api/ocdsReleasePackages",
        page_size=2,
        max_pages_per_window=3,
        max_windows_per_sync=4,
        window_minutes=60,
        initial_lookback_minutes=60,
        overlap_minutes=5,
    )
    values.update(overrides)
    return OCDSOpaqueCursorConfig(**values)


def _params(start, end):
    return {"updatedFrom": start.isoformat(), "updatedTo": end.isoformat()}


def _normalizer(release, now=None):
    return {"external_id": release["ocid"], "source": "UK_PROCUREMENT"}


def test_opaque_next_cursor_is_used_only_inside_window_and_watermark_is_temporal():
    next_url = "https://example.gov/api/ocdsReleasePackages?limit=2&cursor=abc123"
    session = FakeSession([
        FakeResponse({"releases": [{"ocid": "a"}, {"ocid": "b"}], "links": {"next": next_url}}),
        FakeResponse({"releases": [{"ocid": "c"}]}),
    ])
    adapter = OCDSOpaqueCursorAdapter(_config(), params_factory=_params, normalizer=_normalizer, session=session)
    now = datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc)

    rows, cursor = adapter.fetch_incremental(now=now)

    assert [row["external_id"] for row in rows] == ["a", "b", "c"]
    assert "cursor" not in session.calls[0][1]
    assert session.calls[1][1]["cursor"] == "abc123"
    parsed = OCDSOpaqueWindowCursor.decode(cursor)
    assert parsed.completed_through == "2026-08-24T11:00:00Z"
    assert "abc123" not in cursor


def test_subdaily_watermark_replays_only_configured_overlap_minutes_and_finishes_to_now():
    session = FakeSession([FakeResponse({"releases": []}), FakeResponse({"releases": []})])
    adapter = OCDSOpaqueCursorAdapter(_config(window_minutes=15, overlap_minutes=5), params_factory=_params, normalizer=_normalizer, session=session)
    watermark = OCDSOpaqueWindowCursor("2026-08-24T10:30:00Z").encode()
    now = datetime(2026, 8, 24, 10, 45, tzinfo=timezone.utc)

    _, cursor = adapter.fetch_incremental(watermark=watermark, now=now)

    assert len(session.calls) == 2
    first = session.calls[0][1]
    second = session.calls[1][1]
    assert first["updatedFrom"].startswith("2026-08-24T10:25:00")
    assert first["updatedTo"].startswith("2026-08-24T10:40:00")
    assert second["updatedFrom"].startswith("2026-08-24T10:40:00")
    assert second["updatedTo"].startswith("2026-08-24T10:45:00")
    assert OCDSOpaqueWindowCursor.decode(cursor).completed_through == "2026-08-24T10:45:00Z"


def test_repeated_cursor_is_rejected_without_completing_window():
    next_url = "https://example.gov/api/ocdsReleasePackages?cursor=same"
    session = FakeSession([
        FakeResponse({"releases": [{"ocid": "a"}], "links": {"next": next_url}}),
        FakeResponse({"releases": [{"ocid": "b"}], "links": {"next": next_url}}),
    ])
    adapter = OCDSOpaqueCursorAdapter(_config(), params_factory=_params, normalizer=_normalizer, session=session)
    with pytest.raises(RuntimeError, match="repeated opaque cursor"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc))


def test_next_link_cannot_escape_configured_api_host_or_path():
    session = FakeSession([
        FakeResponse({"releases": [{"ocid": "a"}], "links": {"next": "https://evil.example/steal?cursor=x"}}),
    ])
    adapter = OCDSOpaqueCursorAdapter(_config(), params_factory=_params, normalizer=_normalizer, session=session)
    with pytest.raises(RuntimeError, match="escaped configured API endpoint"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc))


def test_empty_page_with_next_cursor_fails_closed():
    next_url = "https://example.gov/api/ocdsReleasePackages?cursor=x"
    session = FakeSession([FakeResponse({"releases": [], "links": {"next": next_url}})])
    adapter = OCDSOpaqueCursorAdapter(_config(), params_factory=_params, normalizer=_normalizer, session=session)
    with pytest.raises(RuntimeError, match="empty page with a next cursor"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc))


def test_window_processor_receives_complete_deduplicatable_release_window():
    received = []

    def processor(releases, *, start, end, now):
        received.append(([r["ocid"] for r in releases], start, end, now))
        return [{"source": "UK_PROCUREMENT", "external_id": "resolved"}]

    session = FakeSession([FakeResponse({"releases": [{"ocid": "a"}, {"ocid": "a"}]})])
    adapter = OCDSOpaqueCursorAdapter(_config(), params_factory=_params, window_processor=processor, session=session)
    now = datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc)

    rows, _ = adapter.fetch_incremental(now=now)

    assert rows[0]["external_id"] == "resolved"
    assert received[0][0] == ["a", "a"]


def test_max_pages_refuses_to_advance_incomplete_window():
    next1 = "https://example.gov/api/ocdsReleasePackages?cursor=one"
    next2 = "https://example.gov/api/ocdsReleasePackages?cursor=two"
    session = FakeSession([
        FakeResponse({"releases": [{"ocid": "a"}], "links": {"next": next1}}),
        FakeResponse({"releases": [{"ocid": "b"}], "links": {"next": next2}}),
    ])
    adapter = OCDSOpaqueCursorAdapter(_config(max_pages_per_window=2), params_factory=_params, normalizer=_normalizer, session=session)
    with pytest.raises(RuntimeError, match="max_pages_per_window=2"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-08-24T12:00:00Z", "2026-08-24T12:00:00+00:00"),
        ("2026-08-24T12:00:00+01:00", "2026-08-24T11:00:00+00:00"),
        ("2026-08-24T12:00:00-05:00", "2026-08-24T17:00:00+00:00"),
        ("2026-08-24T12:00:00", None),
        ("not-a-time", None),
        (None, None),
    ],
)
def test_subdaily_instant_parser_requires_explicit_timezone(value, expected):
    parsed = _datetime(value)
    assert (parsed.isoformat() if parsed is not None else None) == expected


def test_internal_utc_cursor_roundtrip_preserves_instant_and_precision():
    stamp = "2026-08-24T10:30:00.123456Z"
    encoded = OCDSOpaqueWindowCursor(stamp).encode()

    decoded = OCDSOpaqueWindowCursor.decode(encoded)

    assert decoded is not None
    assert decoded.completed_through == stamp
    assert _datetime(decoded.completed_through) == datetime(
        2026, 8, 24, 10, 30, 0, 123456, tzinfo=timezone.utc
    )


def test_timezone_naive_subdaily_cursor_is_rejected_instead_of_assumed_utc():
    encoded = OCDSOpaqueWindowCursor("2026-08-24T10:30:00").encode()

    assert OCDSOpaqueWindowCursor.decode(encoded) is None


def test_internal_cursor_writer_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        _cursor_stamp(datetime(2026, 8, 24, 10, 30))
