from datetime import datetime, timezone

import pytest

from poland_bzp import (
    BZP_API,
    BZP_STATS,
    BZPCursor,
    PolandBZPConnector,
    _state_from_contract,
    parse_bzp_cpvs,
    parse_bzp_update_deadline,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def contract(
    tender_id="ocds-148610-work-1",
    object_id="contract-1",
    *,
    order_type="Works",
    published="2026-08-24T08:00:00Z",
    deadline="2026-08-25T06:00:00Z",
):
    return {
        "noticeType": "ContractNotice",
        "noticeNumber": "2026/BZP 00384147/01",
        "bzpNumber": "2026/BZP 00384147",
        "orderType": order_type,
        "tenderType": "1.1.1",
        "publicationDate": published,
        "orderObject": "Roboty budowlane — modernizacja budynku",
        "cpvCode": "45000000-7 (Roboty budowlane),45210000-2 (Roboty budowlane w zakresie budynków)",
        "submittingOffersDate": deadline,
        "organizationName": "Miasto Testowe",
        "organizationCity": "Łódź",
        "organizationProvince": "PL71",
        "organizationCountry": "PL",
        "tenderId": tender_id,
        "objectId": object_id,
        "htmlBody": "<div>raw contract HTML must not survive normalization</div>",
        "contractors": [{"name": "must not survive"}],
    }


def update(
    tender_id="ocds-148610-work-1",
    object_id="update-1",
    *,
    published="2026-08-24T09:00:00Z",
    html_body=None,
):
    return {
        "noticeType": "NoticeUpdateNotice",
        "noticeNumber": "2026/BZP 00385000/01",
        "bzpNumber": "2026/BZP 00385000",
        "orderType": None,
        "publicationDate": published,
        "orderObject": "Roboty budowlane — modernizacja budynku",
        "cpvCode": "",
        "submittingOffersDate": None,
        "tenderId": tender_id,
        "objectId": object_id,
        "htmlBody": html_body or "<div>SEKCJA III ZMIANA OGŁOSZENIA</div><div>zmiana innego pola</div>",
    }


def deadline_update_html(old="2026-08-25 08:00", new="2026-08-26 14:30"):
    return f"""
    <div>8.1. Termin składania ofert</div>
    <div>Przed zmianą:</div><div>{old}</div>
    <div>Po zmianie:</div><div>{new}</div>
    <div>3.4.1.) Opis zmiany, w tym tekst, który należy dodać lub zmienić:</div>
    <div>8.3. Termin otwarcia ofert</div>
    """


def result(
    tender_id="ocds-148610-work-1",
    object_id="result-1",
    *,
    published="2026-08-24T10:00:00Z",
    procedure_result="uniewaznienie",
):
    return {
        "noticeType": "TenderResultNotice",
        "noticeNumber": "2026/BZP 00386000/01",
        "bzpNumber": "2026/BZP 00386000",
        "orderType": "Works",
        "publicationDate": published,
        "orderObject": "Roboty budowlane — modernizacja budynku",
        "cpvCode": "45000000-7 (Roboty budowlane)",
        "procedureResult": procedure_result,
        "tenderId": tender_id,
        "objectId": object_id,
        "contractors": [{"name": "winner not persisted"}],
    }


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class CompleteSession:
    def __init__(self, rows=None, *, mismatch=False):
        self.rows = list(rows or [])
        self.mismatch = mismatch
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        params = dict(params or {})
        self.calls.append((url, params))
        if url == BZP_STATS:
            counts = {name: 0 for name in ("ContractNotice", "NoticeUpdateNotice", "TenderResultNotice")}
            for row in self.rows:
                counts[row["noticeType"]] += 1
            return Response([{"noticeType": key, "numberOfNotices": value} for key, value in counts.items()])
        notice_type = params["NoticeType"]
        rows = [row for row in self.rows if row["noticeType"] == notice_type]
        if self.mismatch and rows:
            rows = rows[:-1]
        return Response(rows)


class SplitSession:
    """Broad interval reports 2 rows; each half is complete with one row."""
    def __init__(self):
        self.calls = []

    @staticmethod
    def _parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def get(self, url, params=None, headers=None, timeout=None):
        params = dict(params or {})
        self.calls.append((url, params))
        start = self._parse(params["PublicationDateFrom"])
        end = self._parse(params["PublicationDateTo"])
        broad = (end - start).total_seconds() > 1800
        if url == BZP_STATS:
            return Response([
                {"noticeType": "ContractNotice", "numberOfNotices": 2 if broad else 1},
                {"noticeType": "NoticeUpdateNotice", "numberOfNotices": 0},
                {"noticeType": "TenderResultNotice", "numberOfNotices": 0},
            ])
        assert not broad
        marker = params["PublicationDateFrom"].replace(":", "-")
        return Response([contract(
            tender_id=f"nonworks-{marker}",
            object_id=f"obj-{marker}",
            order_type="Services",
            published=params["PublicationDateFrom"],
        )])


def test_cpv_parser_preserves_native_codes_and_descriptions():
    parsed = parse_bzp_cpvs(
        "45000000-7 (Roboty budowlane),45210000-2 (Roboty budowlane w zakresie budynków)"
    )
    assert [row["id"] for row in parsed] == ["45000000-7", "45210000-2"]
    assert parsed[0]["description"] == "Roboty budowlane"
    assert "budynków" in parsed[1]["description"]


def test_update_deadline_parser_uses_warsaw_timezone_and_exact_after_value():
    assert parse_bzp_update_deadline(
        deadline_update_html("2026-08-25 08:00", "2026-08-26 14:30")
    ) == "2026-08-26T12:30:00Z"


def test_update_without_section_8_1_does_not_change_deadline():
    assert parse_bzp_update_deadline("<div>3.2. Zmiana innego pola</div>") is None


def test_malformed_section_8_1_fails_closed():
    with pytest.raises(RuntimeError, match="unsupported structure"):
        parse_bzp_update_deadline("<div>8.1. Termin składania ofert</div><div>Po zmianie:</div><div>2026-08-26 14:30</div>")


def test_works_contract_becomes_one_curated_actionable_procedure():
    connector = PolandBZPConnector(session=CompleteSession(), initial_lookback_days=1)
    tracked, closed = {}, {}
    connector._process_events([contract()], tracked, closed)
    rows, active = connector._finalize(tracked, closed, now=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["external_id"] == "ocds-148610-work-1"
    assert row["is_actionable"] is True
    assert row["cpv"] == "45000000-7"
    assert row["taxonomy"] == "CPV"
    assert row["deadline"] == "2026-08-25T06:00:00Z"
    assert row["url"].endswith("/id/contract-1")
    assert row["place"] == "Łódź | PL71 | PL"
    assert "htmlBody" not in row and "contractors" not in row
    assert list(active) == ["ocds-148610-work-1"]


def test_nonworks_contract_does_not_create_opportunity():
    connector = PolandBZPConnector(session=CompleteSession())
    tracked, closed = {}, {}
    connector._process_events([contract(order_type="Services")], tracked, closed)
    rows, active = connector._finalize(tracked, closed, now=NOW)
    assert rows == []
    assert active == {}


def test_update_reuses_tracked_construction_state_and_changes_deadline():
    connector = PolandBZPConnector(session=CompleteSession())
    tracked, closed = {}, {}
    connector._process_events([
        contract(),
        update(html_body=deadline_update_html("2026-08-25 08:00", "2026-08-27 14:30")),
    ], tracked, closed)
    rows, active = connector._finalize(tracked, closed, now=NOW)
    assert len(rows) == 1
    assert rows[0]["deadline"] == "2026-08-27T12:30:00Z"
    assert rows[0]["source_status"] == "NoticeUpdateNotice"
    assert rows[0]["url"].endswith("/id/update-1")
    assert active["ocds-148610-work-1"]["deadline"] == "2026-08-27T12:30:00Z"


def test_unrelated_update_preserves_tracked_deadline():
    connector = PolandBZPConnector(session=CompleteSession())
    state = _state_from_contract(contract(), was_actionable=True)
    tracked, closed = {state["tender_id"]: state}, {}
    connector._process_events([update()], tracked, closed)
    rows, _active = connector._finalize(tracked, closed, now=NOW)
    assert rows[0]["deadline"] == "2026-08-25T06:00:00Z"


def test_tender_result_closes_previously_actionable_procedure():
    connector = PolandBZPConnector(session=CompleteSession())
    state = _state_from_contract(contract(), was_actionable=True)
    tracked, closed = {state["tender_id"]: state}, {}
    connector._process_events([result()], tracked, closed)
    rows, active = connector._finalize(tracked, closed, now=NOW)
    assert active == {}
    assert len(rows) == 1
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "cancelled"
    assert rows[0]["source_status"] == "TenderResultNotice"
    assert "contractors" not in rows[0]


def test_contract_conclusion_result_is_non_actionable():
    connector = PolandBZPConnector(session=CompleteSession())
    state = _state_from_contract(contract(), was_actionable=True)
    tracked, closed = {state["tender_id"]: state}, {}
    connector._process_events([result(procedure_result="zawarcieUmowy;uniewaznienie")], tracked, closed)
    rows, _active = connector._finalize(tracked, closed, now=NOW)
    assert rows[0]["lifecycle_status"] == "contract_concluded"
    assert rows[0]["is_actionable"] is False


def test_expired_previously_visible_state_emits_tombstone():
    old = contract(deadline="2026-08-24T11:00:00Z")
    state = _state_from_contract(old, was_actionable=True)
    connector = PolandBZPConnector(session=CompleteSession())
    rows, active = connector._finalize({state["tender_id"]: state}, {}, now=NOW)
    assert active == {}
    assert rows[0]["lifecycle_status"] == "deadline_elapsed"
    assert rows[0]["_lifecycle_only"] is True


def test_historical_expired_contract_can_be_extended_before_finalization():
    connector = PolandBZPConnector(session=CompleteSession())
    old = contract(
        published="2026-08-10T08:00:00Z",
        deadline="2026-08-20T06:00:00Z",
    )
    later = update(
        published="2026-08-21T09:00:00Z",
        html_body=deadline_update_html("2026-08-20 08:00", "2026-08-28 10:00"),
    )
    tracked, closed = {}, {}
    connector._process_events([later, old], tracked, closed)
    rows, active = connector._finalize(tracked, closed, now=NOW)
    assert len(rows) == 1
    assert rows[0]["is_actionable"] is True
    assert rows[0]["deadline"] == "2026-08-28T08:00:00Z"
    assert "ocds-148610-work-1" in active


def test_contract_and_result_in_same_sync_never_emit_intermediate_live_row():
    connector = PolandBZPConnector(session=CompleteSession())
    tracked, closed = {}, {}
    connector._process_events([contract(), result()], tracked, closed)
    rows, active = connector._finalize(tracked, closed, now=NOW)
    assert active == {}
    assert rows == []


def test_stats_and_list_must_match_before_cursor_can_advance():
    session = CompleteSession([contract()], mismatch=True)
    connector = PolandBZPConnector(
        session=session,
        initial_lookback_days=1,
        overlap_minutes=0,
        max_windows_per_sync=1,
    )
    with pytest.raises(RuntimeError, match="stats/list mismatch.*cursor not advanced"):
        connector.fetch_incremental(now=NOW)


def test_oversized_interval_is_split_until_each_leaf_is_complete():
    session = SplitSession()
    connector = PolandBZPConnector(
        session=session,
        max_page_size=1,
        initial_lookback_days=1,
        overlap_minutes=0,
        max_window_days=1,
        max_windows_per_sync=1,
    )
    rows, cursor = connector.fetch_incremental(
        watermark="2026-08-24T11:00:00Z",
        now=NOW,
    )
    assert rows == []
    assert BZPCursor.decode(cursor).completed_through == "2026-08-24T12:00:00Z"
    stats_calls = [call for call in session.calls if call[0] == BZP_STATS]
    list_calls = [call for call in session.calls if call[0] == BZP_API]
    assert len(stats_calls) == 3
    assert len(list_calls) == 2


def test_request_hard_limit_fails_without_returning_cursor():
    connector = PolandBZPConnector(
        session=SplitSession(),
        max_page_size=1,
        max_requests_per_sync=1,
        overlap_minutes=0,
    )
    with pytest.raises(RuntimeError, match="max_requests_per_sync=1.*cursor not advanced"):
        connector.fetch_incremental(
            watermark="2026-08-24T11:00:00Z",
            now=NOW,
        )


def test_cursor_roundtrip_and_legacy_timestamp_decode():
    state = _state_from_contract(contract(), was_actionable=True)
    encoded = BZPCursor("2026-08-24T11:00:00Z", {state["tender_id"]: state}, {}).encode()
    decoded = BZPCursor.decode(encoded)
    assert decoded.completed_through == "2026-08-24T11:00:00Z"
    assert decoded.tracked[state["tender_id"]]["object_id"] == "contract-1"
    legacy = BZPCursor.decode("2026-08-24T11:00:00Z")
    assert legacy.tracked == {}
    assert legacy.closed == {}


def test_partial_catchup_persists_pending_state_without_publishing_it():
    state = _state_from_contract(contract(deadline="2026-08-25T06:00:00Z"), was_actionable=True)
    watermark = BZPCursor("2026-08-20T12:00:00Z", {state["tender_id"]: state}, {}).encode()
    connector = PolandBZPConnector(
        session=CompleteSession([]),
        overlap_minutes=0,
        max_window_days=1,
        max_windows_per_sync=1,
    )
    rows, cursor = connector.fetch_incremental(watermark=watermark, now=NOW)
    decoded = BZPCursor.decode(cursor)
    assert rows == []
    assert decoded.completed_through == "2026-08-21T12:00:00Z"
    assert state["tender_id"] in decoded.tracked


def test_complete_fetch_returns_only_final_active_state_and_durable_cursor():
    session = CompleteSession([
        contract(),
        update(html_body=deadline_update_html("2026-08-25 08:00", "2026-08-27 14:30")),
    ])
    connector = PolandBZPConnector(
        session=session,
        overlap_minutes=0,
        max_windows_per_sync=1,
    )
    rows, cursor = connector.fetch_incremental(
        watermark="2026-08-24T07:00:00Z",
        now=NOW,
    )
    assert len(rows) == 1
    assert rows[0]["deadline"] == "2026-08-27T12:30:00Z"
    decoded = BZPCursor.decode(cursor)
    assert decoded.completed_through == "2026-08-24T12:00:00Z"
    assert list(decoded.tracked) == ["ocds-148610-work-1"]
    assert decoded.closed == {}
