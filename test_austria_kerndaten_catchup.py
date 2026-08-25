from datetime import datetime, timedelta, timezone
import json

import pytest

from austria_kerndaten_incremental import (
    AustriaKerndatenIncrementalConnector,
    AustriaKerndatenIncrementalCursor,
)


KDQ = "https://publisher.example/kdq.xml"
DATASET = "dataset-at-catchup"
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def legacy_xml(reference, *, title=None, deadline="2026-09-30T12:00:00+02:00"):
    title = title or f"Bauauftrag {reference}"
    return f"""<KD_8_1_Z2>
      <CONTRACTING_BODY>
        <ADDRESS_CONTRACTING_BODY><OFFICIALNAME>Stadt Test</OFFICIALNAME><NATIONALID>AT-TEST</NATIONALID></ADDRESS_CONTRACTING_BODY>
        <URL_DOCUMENT>https://publisher.example/human/{reference}</URL_DOCUMENT>
      </CONTRACTING_BODY>
      <OBJECT_CONTRACT>
        <TITLE><P>{title}</P></TITLE><REFERENCE_NUMBER>{reference}</REFERENCE_NUMBER>
        <CPV_MAIN><CPV_CODE CODE="45000000"/></CPV_MAIN><TYPE_CONTRACT CTYPE="WORKS"/>
        <SHORT_DESCR><P>{title}</P></SHORT_DESCR><NO_LOT_DIVISION/>
        <OBJECT_DESCR><NUTS CODE="AT13"/></OBJECT_DESCR>
      </OBJECT_CONTRACT>
      <PROCEDURE><PT_OPEN/><DATETIME_RECEIPT_TENDERS>{deadline}</DATETIME_RECEIPT_TENDERS></PROCEDURE>
      <ADDITIONAL_CORE_DATA><DATE_FIRST_PUBLICATION>2026-08-01</DATE_FIRST_PUBLICATION><DATETIME_LAST_CHANGE>2026-08-24T10:00:00+02:00</DATETIME_LAST_CHANGE></ADDITIONAL_CORE_DATA>
    </KD_8_1_Z2>""".encode()


class DummySession:
    def __init__(self):
        self.headers = {}


class FakeConnector(AustriaKerndatenIncrementalConnector):
    def __init__(self, *, items, payloads, **kwargs):
        super().__init__(session=DummySession(), **kwargs)
        self.items = items
        self.payloads = payloads
        self.notice_calls = []

    def _discover(self, cursor):
        return {DATASET: {"urls": [KDQ]}}

    def _kdq_items(self, url):
        assert url == KDQ
        return list(self.items)

    def _notice_payload(self, url):
        self.notice_calls.append(url)
        value = self.payloads[url]
        if isinstance(value, Exception):
            raise value
        return value


def item(number, modified):
    url = f"https://publisher.example/{number}.xml"
    return {"id": f"pub-{number}", "lastmod": modified, "url": url}


def fixture(count=5):
    items = []
    payloads = {}
    for number in range(count):
        modified = f"2026-08-24T{8 + number:02d}:00:00+00:00"
        row = item(number, modified)
        items.append(row)
        payloads[row["url"]] = legacy_xml(f"R-{number}")
    return items, payloads


def test_large_initial_window_is_split_across_runs_without_partial_emission():
    items, payloads = fixture(5)
    connector = FakeConnector(
        items=items,
        payloads=payloads,
        max_notice_fetches_per_run=2,
        # Prove the old per-KDQ threshold no longer hard-fails the bootstrap.
        max_notice_fetches_per_kdq=1,
    )

    rows1, cursor1 = connector.fetch_incremental(now=NOW)
    state1 = AustriaKerndatenIncrementalCursor.decode(cursor1)
    assert rows1 == []
    assert state1.observed_through == ""
    assert state1.catchup["through"] == "2026-08-24T12:00:00Z"
    assert len(state1.catchup["pending"]) == 2
    assert len(connector.notice_calls) == 2

    rows2, cursor2 = connector.fetch_incremental(watermark=cursor1, now=NOW + timedelta(hours=1))
    state2 = AustriaKerndatenIncrementalCursor.decode(cursor2)
    assert rows2 == []
    assert state2.observed_through == ""
    assert len(state2.catchup["pending"]) == 4
    assert len(connector.notice_calls) == 4

    rows3, cursor3 = connector.fetch_incremental(watermark=cursor2, now=NOW + timedelta(hours=2))
    state3 = AustriaKerndatenIncrementalCursor.decode(cursor3)
    assert len(rows3) == 5
    assert all(row["is_actionable"] for row in rows3)
    assert state3.catchup == {}
    assert state3.observed_through == "2026-08-24T12:00:00Z"
    assert len(state3.tracked) == 5
    assert len(connector.notice_calls) == 5


def test_catchup_horizon_is_frozen_and_newer_item_waits_for_next_cycle():
    old1 = item(1, "2026-08-24T10:00:00+00:00")
    old2 = item(2, "2026-08-24T11:00:00+00:00")
    newer = item(3, "2026-08-24T12:30:00+00:00")
    payloads = {
        old1["url"]: legacy_xml("R-1"),
        old2["url"]: legacy_xml("R-2"),
        newer["url"]: legacy_xml("R-3"),
    }
    # This test isolates the frozen-horizon invariant. Overlap behavior is a
    # separate concern and would intentionally rehydrate older publications.
    connector = FakeConnector(
        items=[old1, old2],
        payloads=payloads,
        max_notice_fetches_per_run=1,
        overlap_hours=0,
    )

    rows1, cursor1 = connector.fetch_incremental(now=NOW)
    assert rows1 == []

    connector.items = [old1, old2, newer]
    later = NOW + timedelta(hours=1)
    rows2, cursor2 = connector.fetch_incremental(watermark=cursor1, now=later)
    assert {row["procedure_reference"] for row in rows2} == {"R-1", "R-2"}
    state2 = AustriaKerndatenIncrementalCursor.decode(cursor2)
    assert state2.observed_through == "2026-08-24T12:00:00Z"

    rows3, cursor3 = connector.fetch_incremental(watermark=cursor2, now=later)
    assert {row["procedure_reference"] for row in rows3} == {"R-3"}
    assert AustriaKerndatenIncrementalCursor.decode(cursor3).observed_through == "2026-08-24T13:00:00Z"


def test_v1_cursor_is_read_and_upgraded_without_losing_state():
    old = json.dumps(
        {
            "version": 1,
            "observed_through": "2026-08-23T12:00:00Z",
            "datasets": {DATASET: {"urls": [KDQ]}},
            "kdq_observed": {KDQ: "2026-08-23T12:00:00Z"},
            "tracked": {"old": {"external_id": "old", "was_visible": True}},
        }
    )
    decoded = AustriaKerndatenIncrementalCursor.decode(old)
    assert decoded.catchup == {}
    assert decoded.tracked["old"]["was_visible"] is True
    assert json.loads(decoded.encode())["version"] == 2


def test_failed_first_notice_is_hard_failure_and_returns_no_advanced_cursor():
    row = item(1, "2026-08-24T10:00:00+00:00")
    connector = FakeConnector(
        items=[row],
        payloads={row["url"]: RuntimeError("publisher failure")},
        max_notice_fetches_per_run=1,
    )
    with pytest.raises(RuntimeError, match="catchup made no progress; cursor not advanced"):
        connector.fetch_incremental(now=NOW)


def test_existing_visible_state_is_not_reemitted_while_new_backlog_is_partial():
    seed_item = item(0, "2026-08-23T10:00:00+00:00")
    payloads = {seed_item["url"]: legacy_xml("R-0")}
    seed = FakeConnector(items=[seed_item], payloads=payloads, max_notice_fetches_per_run=10)
    seed_rows, watermark = seed.fetch_incremental(now=NOW - timedelta(days=1))
    assert len(seed_rows) == 1

    backlog, more_payloads = fixture(3)
    payloads.update(more_payloads)
    connector = FakeConnector(items=backlog, payloads=payloads, max_notice_fetches_per_run=1)
    rows, cursor = connector.fetch_incremental(watermark=watermark, now=NOW)
    assert rows == []
    state = AustriaKerndatenIncrementalCursor.decode(cursor)
    assert state.catchup
    assert any(value.get("was_visible") for value in state.tracked.values())