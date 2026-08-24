from datetime import datetime, timezone

import pytest

from uruguay_arce import ARCEOCDSRSSAdapter, ARCE_RECORD_ROOT, ARCE_RSS_URL


class FakeResponse:
    def __init__(self, *, content=b"", payload=None, status=200):
        self.content = content
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def get(self, url, *, headers, timeout):
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected URL {url}")
        return self.responses[url]


def _rss(items):
    body = ['<?xml version="1.0" encoding="UTF-8"?><rss><channel><title>ARCE</title>']
    for item in items:
        body.append(
            "<item>"
            f"<title>{item['title']}</title>"
            f"<pubDate>{item['pubDate']}</pubDate>"
            f"<link>{item['link']}</link>"
            f"<guid>{item['guid']}</guid>"
            f"<category>{item['category']}</category>"
            "</item>"
        )
    body.append("</channel></rss>")
    return "".join(body).encode()


def _release(release_id, date, tender):
    return {"version": "1.1", "releases": [{"ocid": "ocds-yfs5dr-100", "id": release_id, "date": date, "tag": ["tenderUpdate"], "tender": tender}]}


def test_empty_current_feed_fails_closed_without_cursor_advance():
    session = FakeSession({ARCE_RSS_URL: FakeResponse(content=_rss([]))})
    adapter = ARCEOCDSRSSAdapter(session=session)

    with pytest.raises(RuntimeError, match="current RSS returned no events; cursor not advanced"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))

    assert session.calls == [ARCE_RSS_URL]


def test_same_second_release_refs_use_natural_sequence_not_record_array_order():
    current_feed = _rss([
        {
            "title": "id_compra:100,release_id:aclar_llamado-100-1",
            "pubDate": "Mon, 24 Aug 2026 09:00:00",
            "link": "http://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-1",
            "guid": "aclar_llamado-100-1",
            "category": "tenderUpdate",
        }
    ])
    record = {
        "records": [{
            "ocid": "ocds-yfs5dr-100",
            "releases": [
                {"url": "http://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-1", "date": "2026-08-24T09:00:00Z", "tag": ["tenderUpdate"]},
                {"url": "http://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-0", "date": "2026-08-24T09:00:00Z", "tag": ["tenderUpdate"]},
                {"url": "http://www.comprasestatales.gub.uy/ocds/release/llamado-100", "date": "2026-08-24T08:00:00Z", "tag": ["tender"]},
            ],
        }]
    }
    initial = {
        "version": "1.1",
        "releases": [{
            "ocid": "ocds-yfs5dr-100",
            "id": "llamado-100",
            "date": "2026-08-24T08:00:00Z",
            "tag": ["tender"],
            "tender": {
                "id": "100",
                "title": "Obra vial",
                "status": "active",
                "tenderPeriod": {"endDate": "2026-08-30T11:00:00Z"},
                "items": [{"id": "i1", "classification": {"scheme": "UNSPSC", "id": "72141000"}}],
            },
        }],
    }
    seq0 = _release("aclar_llamado-100-0", "2026-08-24T09:00:00Z", {"id": "100", "description": "primeiro"})
    seq1 = _release("aclar_llamado-100-1", "2026-08-24T09:00:00Z", {"id": "100", "description": "segundo"})

    release_initial = "https://www.comprasestatales.gub.uy/ocds/release/llamado-100"
    release_0 = "https://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-0"
    release_1 = "https://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-1"
    session = FakeSession({
        ARCE_RSS_URL: FakeResponse(content=current_feed),
        f"{ARCE_RECORD_ROOT}/100": FakeResponse(payload=record),
        release_initial: FakeResponse(payload=initial),
        release_0: FakeResponse(payload=seq0),
        release_1: FakeResponse(payload=seq1),
    })
    adapter = ARCEOCDSRSSAdapter(session=session)

    state = adapter._hydrate_tender_state("100")

    assert [url for url in session.calls if "/ocds/release/" in url] == [release_initial, release_0, release_1]
    assert state["compiledRelease"]["tender"]["description"] == "segundo"
