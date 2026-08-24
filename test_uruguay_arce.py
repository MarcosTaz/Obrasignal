from datetime import datetime, timezone
import json

import pytest

import uruguay_arce
from uruguay_arce import (
    ARCECursor,
    ARCEOCDSRSSAdapter,
    ARCE_RECORD_ROOT,
    ARCE_RSS_URL,
    merge_arce_releases,
    monthly_rss_url,
    normalize_arce_process,
    parse_arce_rss,
    purchase_id_from_title,
)


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
        self.calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
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
            f"<link>{item.get('link', 'http://www.comprasestatales.gub.uy/ocds/release/x')}</link>"
            f"<guid>{item['guid']}</guid>"
            f"<category>{item['category']}</category>"
            "</item>"
        )
    body.append("</channel></rss>")
    return "".join(body).encode()


def _initial_release(*, deadline="2026-08-30T11:00:00Z", status="active"):
    return {
        "ocid": "ocds-yfs5dr-100",
        "id": "llamado-100",
        "date": "2026-08-24T08:00:00Z",
        "tag": ["tender"],
        "buyer": {"name": "Intendencia de Prueba"},
        "tender": {
            "id": "100",
            "title": "Reparación de puente y obra vial",
            "description": "Obras de infraestructura",
            "status": status,
            "procurementMethod": "open",
            "procurementMethodDetails": "Concurso de Precios",
            "tenderPeriod": {"endDate": deadline},
            "items": [
                {
                    "id": "item-1",
                    "description": "Obra vial",
                    "classification": {"scheme": "UNSPSC", "id": "72141000"},
                }
            ],
        },
    }


def _update_release():
    return {
        "ocid": "ocds-yfs5dr-100",
        "id": "aclar_llamado-100-1",
        "date": "2026-08-24T09:00:00Z",
        "tag": ["tenderUpdate"],
        "tender": {
            "id": "100",
            "amendments": [{"id": "a1", "date": "2026-08-24T09:00:00Z"}],
            "documents": [{"id": "d1", "title": "Aclaración"}],
        },
    }


def _record_package(*, refs=None):
    refs = refs or [
        {"url": "http://www.comprasestatales.gub.uy/ocds/release/llamado-100", "date": "2026-08-24T08:00:00Z", "tag": ["tender"]},
        {"url": "http://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-1", "date": "2026-08-24T09:00:00Z", "tag": ["tenderUpdate"]},
    ]
    return {"records": [{"ocid": "ocds-yfs5dr-100", "releases": refs}]}


def _release_package(release):
    return {"version": "1.1", "releases": [release]}


def test_purchase_id_parser_is_key_based_not_position_based():
    assert purchase_id_from_title("id_compra:1363136,release_id:x") == "1363136"
    assert purchase_id_from_title(" release_id:x, id_compra : ABC-12 ") == "ABC-12"
    assert purchase_id_from_title("release_id:x") == ""


def test_rss_parser_orders_events_and_normalizes_links():
    events = parse_arce_rss(_rss([
        {"title": "id_compra:2,release_id:b", "pubDate": "Mon, 24 Aug 2026 10:00:01", "guid": "b", "category": "awardUpdate"},
        {"title": "id_compra:1,release_id:a", "pubDate": "Mon, 24 Aug 2026 10:00:00", "guid": "a", "category": "tenderUpdate"},
    ]))
    assert [event.guid for event in events] == ["a", "b"]
    assert events[0].purchase_id == "1"
    assert events[0].published_at == "2026-08-24T10:00:00Z"
    assert events[0].link.startswith("https://")


def test_merge_partial_tender_update_keeps_omitted_initial_fields():
    merged = merge_arce_releases([_initial_release(), _update_release()])
    assert merged["tender"]["status"] == "active"
    assert merged["tender"]["title"] == "Reparación de puente y obra vial"
    assert merged["tender"]["tenderPeriod"]["endDate"] == "2026-08-30T11:00:00Z"
    assert merged["tender"]["amendments"][0]["id"] == "a1"
    assert merged["tag"] == ["tender", "tenderUpdate"]
    assert merged["date"] == "2026-08-24T09:00:00Z"


def test_merge_nested_explicit_update_changes_deadline_and_merges_id_array():
    update = _update_release()
    update["tender"]["tenderPeriod"] = {"endDate": "2026-09-02T11:00:00Z"}
    update["tender"]["items"] = [{"id": "item-1", "description": "Obra vial actualizada"}]
    merged = merge_arce_releases([_initial_release(), update])
    assert merged["tender"]["tenderPeriod"]["endDate"] == "2026-09-02T11:00:00Z"
    assert merged["tender"]["items"][0]["description"] == "Obra vial actualizada"
    assert merged["tender"]["items"][0]["classification"]["id"] == "72141000"


def test_normalizer_requires_active_and_future_deadline():
    future = {"ocid": "ocds-yfs5dr-100", "compiledRelease": _initial_release(), "uri": f"{ARCE_RECORD_ROOT}/100"}
    item = normalize_arce_process(future, purchase_id="100", now=datetime(2026, 8, 24, tzinfo=timezone.utc))
    assert item is not None
    assert item["source"] == "UY_ARCE"
    assert item["taxonomy"] == "UNSPSC"
    assert item["cpv"] == ""
    assert item["license"] == uruguay_arce.ARCE_LICENSE
    assert item["source_reference"] == "100"

    expired_release = _initial_release(deadline="2026-08-20T11:00:00Z")
    expired = {"ocid": "ocds-yfs5dr-100", "compiledRelease": expired_release}
    assert normalize_arce_process(expired, purchase_id="100", now=datetime(2026, 8, 24, tzinfo=timezone.utc)) is None

    completed_release = _initial_release(status="complete")
    completed = {"ocid": "ocds-yfs5dr-100", "compiledRelease": completed_release}
    assert normalize_arce_process(completed, purchase_id="100", now=datetime(2026, 8, 24, tzinfo=timezone.utc)) is None


def test_adapter_hydrates_one_purchase_once_and_ignores_non_tender_event():
    feed = _rss([
        {"title": "id_compra:100,release_id:llamado-100", "pubDate": "Mon, 24 Aug 2026 08:00:00", "guid": "llamado-100", "category": "tender"},
        {"title": "id_compra:100,release_id:aclar-100", "pubDate": "Mon, 24 Aug 2026 09:00:00", "guid": "aclar-100", "category": "tenderUpdate"},
        {"title": "id_compra:200,release_id:award-200", "pubDate": "Mon, 24 Aug 2026 09:30:00", "guid": "award-200", "category": "awardUpdate"},
    ])
    responses = {
        ARCE_RSS_URL: FakeResponse(content=feed),
        f"{ARCE_RECORD_ROOT}/100": FakeResponse(payload=_record_package()),
        "https://www.comprasestatales.gub.uy/ocds/release/llamado-100": FakeResponse(payload=_release_package(_initial_release())),
        "https://www.comprasestatales.gub.uy/ocds/release/aclar_llamado-100-1": FakeResponse(payload=_release_package(_update_release())),
    }
    session = FakeSession(responses)
    adapter = ARCEOCDSRSSAdapter(session=session, initial_lookback_hours=24)
    rows, cursor = adapter.fetch_incremental(now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))

    assert len(rows) == 1
    assert rows[0]["external_id"] == "ocds-yfs5dr-100"
    assert sum(call["url"] == f"{ARCE_RECORD_ROOT}/100" for call in session.calls) == 1
    parsed_cursor = ARCECursor.decode(cursor)
    assert parsed_cursor.published_at == "2026-08-24T09:30:00Z"


def test_adapter_fails_closed_when_release_history_exceeds_bound():
    feed = _rss([
        {"title": "id_compra:100,release_id:x", "pubDate": "Mon, 24 Aug 2026 09:00:00", "guid": "x", "category": "tenderUpdate"},
    ])
    refs = [
        {"url": f"http://www.comprasestatales.gub.uy/ocds/release/r-{index}", "date": f"2026-08-24T09:{index:02d}:00Z", "tag": ["tenderUpdate"]}
        for index in range(3)
    ]
    session = FakeSession({
        ARCE_RSS_URL: FakeResponse(content=feed),
        f"{ARCE_RECORD_ROOT}/100": FakeResponse(payload=_record_package(refs=refs)),
    })
    adapter = ARCEOCDSRSSAdapter(session=session, max_release_refs_per_process=2)
    with pytest.raises(RuntimeError, match="above max_release_refs_per_process"):
        adapter.fetch_incremental(now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))


def test_monthly_recovery_advances_completed_past_month_and_next_sync_uses_next_month():
    current_feed = _rss([
        {"title": "id_compra:900,release_id:new", "pubDate": "Mon, 24 Aug 2026 09:00:00", "guid": "new", "category": "awardUpdate"},
    ])
    july_feed = _rss([
        {"title": "id_compra:800,release_id:old", "pubDate": "Mon, 06 Jul 2026 09:00:00", "guid": "old", "category": "awardUpdate"},
    ])
    august_feed = _rss([
        {"title": "id_compra:801,release_id:aug", "pubDate": "Sat, 01 Aug 2026 09:00:00", "guid": "aug", "category": "awardUpdate"},
    ])
    july_url = monthly_rss_url(datetime(2026, 7, 5, tzinfo=timezone.utc))
    august_url = monthly_rss_url(datetime(2026, 8, 1, tzinfo=timezone.utc))
    session = FakeSession({
        ARCE_RSS_URL: FakeResponse(content=current_feed),
        july_url: FakeResponse(content=july_feed),
        august_url: FakeResponse(content=august_feed),
    })
    adapter = ARCEOCDSRSSAdapter(session=session)
    cursor = ARCECursor("2026-07-05T00:00:00Z", "x").encode()
    rows, july_cursor = adapter.fetch_incremental(watermark=cursor, now=datetime(2026, 8, 24, tzinfo=timezone.utc))
    assert rows == []
    completed = ARCECursor.decode(july_cursor)
    assert completed.published_at == "2026-07-31T23:59:59Z"
    assert completed.guid == "~"

    adapter.fetch_incremental(watermark=july_cursor, now=datetime(2026, 8, 24, tzinfo=timezone.utc))
    assert any(call["url"] == august_url for call in session.calls)


def test_cursor_round_trip():
    cursor = ARCECursor("2026-08-24T10:00:00Z", "guid-1")
    assert ARCECursor.decode(cursor.encode()) == cursor
    assert ARCECursor.decode("bad") is None
