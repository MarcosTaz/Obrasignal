from datetime import datetime, timezone

from poland_bzp import BZPCursor, PolandBZPConnector, _state_from_contract


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def contract(*, deadline):
    return {
        "noticeType": "ContractNotice",
        "noticeNumber": "2026/BZP 00384147/01",
        "bzpNumber": "2026/BZP 00384147",
        "orderType": "Works",
        "tenderType": "1.1.1",
        "publicationDate": "2026-08-24T08:00:00Z",
        "orderObject": "Roboty budowlane — modernizacja budynku",
        "cpvCode": "45000000-7 (Roboty budowlane)",
        "submittingOffersDate": deadline,
        "organizationName": "Miasto Testowe",
        "organizationCity": "Łódź",
        "organizationProvince": "PL71",
        "organizationCountry": "PL",
        "tenderId": "ocds-148610-work-1",
        "objectId": "contract-1",
    }


def deadline_update_html(old="2026-08-25 08:00", new="2026-08-27 14:30"):
    return f"""
    <div>8.1. Termin składania ofert</div>
    <div>Przed zmianą:</div><div>{old}</div>
    <div>Po zmianie:</div><div>{new}</div>
    """


def update():
    return {
        "noticeType": "NoticeUpdateNotice",
        "noticeNumber": "2026/BZP 00385000/01",
        "bzpNumber": "2026/BZP 00385000",
        "orderType": None,
        "publicationDate": "2026-08-24T09:00:00Z",
        "orderObject": "Roboty budowlane — modernizacja budynku",
        "cpvCode": "",
        "submittingOffersDate": None,
        "tenderId": "ocds-148610-work-1",
        "objectId": "update-1",
        "htmlBody": deadline_update_html(),
    }


class EmptyResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class EmptySession:
    def get(self, url, params=None, headers=None, timeout=None):
        if url.endswith("/stats"):
            return EmptyResponse([
                {"noticeType": "ContractNotice", "numberOfNotices": 0},
                {"noticeType": "NoticeUpdateNotice", "numberOfNotices": 0},
                {"noticeType": "TenderResultNotice", "numberOfNotices": 0},
            ])
        return EmptyResponse([])


def test_default_page_size_stays_at_live_proven_250():
    assert PolandBZPConnector(session=EmptySession()).max_page_size == 250


def test_historical_pending_cursor_does_not_become_fake_actionable_tombstone():
    state = _state_from_contract(
        contract(deadline="2026-08-24T10:00:00Z"),
        was_actionable=False,
    )
    watermark = BZPCursor(
        "2026-08-24T11:55:00Z",
        {state["tender_id"]: state},
        {},
    ).encode()
    connector = PolandBZPConnector(
        session=EmptySession(),
        overlap_minutes=0,
        max_window_days=1,
        max_windows_per_sync=1,
    )

    rows, cursor = connector.fetch_incremental(watermark=watermark, now=NOW)

    assert rows == []
    decoded = BZPCursor.decode(cursor)
    assert decoded.tracked == {}
    assert decoded.closed == {}


def test_missing_deadline_works_state_is_kept_pending_for_later_update():
    connector = PolandBZPConnector(session=EmptySession())
    state = _state_from_contract(contract(deadline=None), was_actionable=False)

    rows, survivors = connector._finalize(
        {state["tender_id"]: state},
        {},
        now=NOW,
    )
    assert rows == []
    assert state["tender_id"] in survivors
    assert survivors[state["tender_id"]]["was_actionable"] is False

    tracked = survivors
    closed = {}
    connector._process_events([update()], tracked, closed)
    rows, survivors = connector._finalize(tracked, closed, now=NOW)

    assert len(rows) == 1
    assert rows[0]["is_actionable"] is True
    assert rows[0]["deadline"] == "2026-08-27T12:30:00Z"
    assert state["tender_id"] in survivors


def test_missing_deadline_tombstone_is_emitted_once_then_remains_pending():
    connector = PolandBZPConnector(session=EmptySession())
    state = _state_from_contract(contract(deadline=None), was_actionable=True)

    first_rows, survivors = connector._finalize(
        {state["tender_id"]: state},
        {},
        now=NOW,
    )
    assert len(first_rows) == 1
    assert first_rows[0]["lifecycle_status"] == "deadline_missing"
    assert first_rows[0]["_lifecycle_only"] is True
    assert survivors[state["tender_id"]]["was_actionable"] is False

    second_rows, survivors_again = connector._finalize(survivors, {}, now=NOW)
    assert second_rows == []
    assert state["tender_id"] in survivors_again
