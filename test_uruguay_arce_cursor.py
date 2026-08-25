from datetime import datetime, timezone

from uruguay_arce import ARCECursor, ARCEOCDSRSSAdapter, ARCE_RSS_URL


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, content):
        self.content = content

    def get(self, url, *, headers, timeout):
        assert url == ARCE_RSS_URL
        return FakeResponse(self.content)


def _rss():
    items = [
        ("a", "Mon, 24 Aug 2026 09:00:00"),
        ("b", "Mon, 24 Aug 2026 09:00:01"),
        ("c", "Mon, 24 Aug 2026 09:00:01"),
        ("d", "Mon, 24 Aug 2026 09:00:02"),
    ]
    body = ['<?xml version="1.0"?><rss><channel>']
    for guid, published in items:
        body.append(
            "<item>"
            f"<title>id_compra:900,release_id:{guid}</title>"
            f"<pubDate>{published}</pubDate>"
            f"<link>http://www.comprasestatales.gub.uy/ocds/release/{guid}</link>"
            f"<guid>{guid}</guid>"
            "<category>awardUpdate</category>"
            "</item>"
        )
    body.append("</channel></rss>")
    return "".join(body).encode()


def test_strict_event_cursor_cannot_stall_inside_overlap_window():
    adapter = ARCEOCDSRSSAdapter(
        session=FakeSession(_rss()),
        initial_lookback_hours=24,
        overlap_seconds=2,
        max_events_per_sync=2,
    )
    now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)

    first_rows, first_cursor = adapter.fetch_incremental(now=now)
    assert first_rows == []
    first = ARCECursor.decode(first_cursor)
    assert (first.published_at, first.guid) == ("2026-08-24T09:00:01Z", "b")

    second_rows, second_cursor = adapter.fetch_incremental(watermark=first_cursor, now=now)
    assert second_rows == []
    second = ARCECursor.decode(second_cursor)
    assert (second.published_at, second.guid) == ("2026-08-24T09:00:02Z", "d")
    assert second_cursor != first_cursor
