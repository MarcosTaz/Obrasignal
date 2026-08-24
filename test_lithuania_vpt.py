from datetime import datetime, timezone
import json

import pytest
import requests

from lithuania_vpt import (
    ENDPOINT,
    PUBLIC_API_KEY,
    LithuaniaVPTCursor,
    LithuaniaVPTSnapshotConnector,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def row(
    ident,
    *,
    procurement_type="Works",
    status="Bid submission",
    procedure="Open",
    deadline="07-09-2026 08:00:00",
    published="23-08-2026 06:33:19",
    cpv="45000000, 71320000",
    title=None,
):
    return {
        "id": ident,
        "cftCaUniqueId": str(ident),
        "cftInvolves": "notice.type.publicContract",
        "caName": "UAB Test Buyer",
        "caNumber": "123456789",
        "datePublished": published,
        "status": status,
        "activeCycle": 1,
        "procurementType": procurement_type,
        "procedure": procedure,
        "cpvCodes": cpv,
        "nutsCode": "LT011",
        "tenderSubmissionDeadline": deadline,
        "title": title or f"Works {ident}",
        "description": f"Description {ident}",
        "estimatedValue": 12345.67,
        "evaluationMechanism": "MEAT",
        "directive": "prompt.directive.classic",
        "euFunding": True,
        "contractDuration": "12_months",
        "tenderValidity": "90_days",
        "contractAwardedInLots": False,
        "awardDate": None,
        "contractAwardDate": None,
        # Must never leak through the curated observation contract.
        "supplierPersonalEmail": "person@example.invalid",
        "rawPrivateThing": {"secret": "not-for-output"},
    }


class FakeResponse:
    def __init__(self, payload=None, *, status=200, json_error=None):
        self.payload = payload
        self.status_code = status
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []

    def post(self, url, *, headers=None, json=None, timeout=None):
        self.calls.append((url, headers, json, timeout))
        page_num = int(json["pageNum"])
        value = self.pages.get(page_num, [])
        if isinstance(value, Exception):
            raise value
        if isinstance(value, FakeResponse):
            return value
        return FakeResponse(value)


def connector(pages, *, page_size=2, max_pages=10):
    session = FakeSession(pages)
    return LithuaniaVPTSnapshotConnector(
        session=session,
        page_size=page_size,
        max_pages=max_pages,
    ), session


def decode(value):
    return LithuaniaVPTCursor.decode(value)


def test_complete_snapshot_pages_until_short_tail_and_uses_public_key():
    c, session = connector({1: [row(1), row(2)], 2: [row(3)]})
    rows, cursor = c.fetch_incremental(now=NOW)

    assert {item["external_id"] for item in rows} == {"1", "2", "3"}
    assert len(session.calls) == 2
    assert all(call[0] == ENDPOINT for call in session.calls)
    assert all(call[1]["apiKey"] == PUBLIC_API_KEY for call in session.calls)
    assert [call[2] for call in session.calls] == [
        {"pageSize": 2, "pageNum": 1},
        {"pageSize": 2, "pageNum": 2},
    ]
    state = decode(cursor)
    assert state.observed_through == "2026-08-24T12:00:00Z"
    assert set(state.tracked) == {"1", "2", "3"}


def test_open_works_is_curated_with_vilnius_deadline_and_human_url():
    c, _ = connector({1: [row(9333230)]})
    rows, _ = c.fetch_incremental(now=NOW)
    assert len(rows) == 1
    item = rows[0]
    assert item["signal_type"] == "TENDER"
    assert item["contract_type"] == "works"
    assert item["is_actionable"] is True
    assert item["deadline"] == "2026-09-07T05:00:00Z"
    assert item["published_at"] == "2026-08-23T03:33:19Z"
    assert item["cpv"] == "45000000"
    assert item["cpv_codes"] == ["45000000", "71320000"]
    assert item["url"].endswith("prepareViewCfTWS.do?resourceId=9333230")
    assert item["buyer_national_id"] == "123456789"
    assert "supplierPersonalEmail" not in item
    assert "rawPrivateThing" not in item


def test_non_works_never_becomes_opportunity():
    c, _ = connector({1: [row(1, procurement_type="Services")]})
    rows, cursor = c.fetch_incremental(now=NOW)
    assert rows == []
    assert decode(cursor).tracked == {}


def test_preliminary_market_consultation_is_structurally_excluded():
    consultation = row(
        9327248,
        status="Proposal Submission",
        procedure="Preliminary Market Consultation",
    )
    c, _ = connector({1: [consultation]})
    rows, cursor = c.fetch_incremental(now=NOW)
    assert rows == []
    assert decode(cursor).tracked == {}


def test_non_bid_status_does_not_become_open_even_with_future_deadline():
    c, _ = connector({1: [row(1, status="Established")]})
    rows, _ = c.fetch_incremental(now=NOW)
    assert rows == []


def test_awarded_status_closes_previously_visible_tender_once():
    first, _ = connector({1: [row(8009747)]})
    open_rows, watermark = first.fetch_incremental(now=NOW)
    assert len(open_rows) == 1

    awarded = row(8009747, status="Awarded", deadline="01-06-2026 10:00:00")
    awarded["awardDate"] = "23-06-2026 12:51:37"
    second, _ = connector({1: [awarded]})
    rows, cursor = second.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "awarded"
    assert rows[0]["is_actionable"] is False
    assert decode(cursor).tracked == {}

    third, _ = connector({1: [awarded]})
    repeated, _ = third.fetch_incremental(watermark=cursor, now=NOW)
    assert repeated == []


def test_cancelled_status_closes_previously_visible_tender():
    first, _ = connector({1: [row(1)]})
    _, watermark = first.fetch_incremental(now=NOW)
    second, _ = connector({1: [row(1, status="Cancelled")]})
    rows, _ = second.fetch_incremental(watermark=watermark, now=NOW)
    assert rows[0]["lifecycle_status"] == "cancelled"
    assert rows[0]["lifecycle_reason"] == "cancelled"


def test_expired_bid_submission_closes_visible_state():
    first, _ = connector({1: [row(1)]})
    _, watermark = first.fetch_incremental(now=NOW)
    second, _ = connector({1: [row(1, deadline="24-08-2026 10:00:00")]})
    rows, _ = second.fetch_incremental(watermark=watermark, now=NOW)
    assert rows[0]["lifecycle_status"] == "deadline_elapsed"


def test_missing_or_invalid_deadline_is_not_actionable_and_can_close_visible_state():
    fresh, _ = connector({1: [row(1, deadline="not-a-date")]})
    rows, cursor = fresh.fetch_incremental(now=NOW)
    assert rows == []
    assert decode(cursor).tracked == {}

    first, _ = connector({1: [row(1)]})
    _, watermark = first.fetch_incremental(now=NOW)
    broken, _ = connector({1: [row(1, deadline="not-a-date")]})
    tombstones, _ = broken.fetch_incremental(watermark=watermark, now=NOW)
    assert tombstones[0]["lifecycle_status"] == "deadline_missing_or_invalid"
    assert tombstones[0]["_lifecycle_only"] is True


def test_missing_from_complete_snapshot_emits_inactive_tombstone():
    first, _ = connector({1: [row(1)]})
    _, watermark = first.fetch_incremental(now=NOW)
    second, _ = connector({1: [row(2)]})
    rows, _ = second.fetch_incremental(watermark=watermark, now=NOW)
    by_id = {item["external_id"]: item for item in rows}
    assert by_id["1"]["lifecycle_status"] == "inactive"
    assert by_id["1"]["lifecycle_reason"] == "missing_from_complete_snapshot"
    assert by_id["2"]["is_actionable"] is True


def test_unchanged_open_state_is_not_reemitted():
    first, _ = connector({1: [row(1)]})
    _, watermark = first.fetch_incremental(now=NOW)
    second, _ = connector({1: [row(1)]})
    rows, _ = second.fetch_incremental(watermark=watermark, now=NOW)
    assert rows == []


def test_changed_open_state_is_emitted_as_updated_open_row():
    first, _ = connector({1: [row(1, title="Old title")]})
    _, watermark = first.fetch_incremental(now=NOW)
    second, _ = connector({1: [row(1, title="Corrected title")]})
    rows, _ = second.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1
    assert rows[0]["title"] == "Corrected title"
    assert rows[0]["is_actionable"] is True


def test_corrupt_legacy_publication_year_does_not_break_valid_current_tender():
    c, _ = connector({1: [row(1, published="14-06-0028 00:00:00")]})
    rows, _ = c.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["published_at"] is None
    assert rows[0]["publication_date"] == ""


def test_placeholder_cft_unique_id_is_not_used_as_procedure_reference():
    value = row(7)
    value["cftCaUniqueId"] = "---"
    c, _ = connector({1: [value]})
    rows, _ = c.fetch_incremental(now=NOW)
    assert rows[0]["cft_ca_unique_id"] == ""
    assert rows[0]["procedure_reference"] == "7"


def test_duplicate_id_across_snapshot_pages_is_hard_failure():
    c, _ = connector({1: [row(1), row(2)], 2: [row(2)]})
    with pytest.raises(RuntimeError, match="duplicate snapshot id 2"):
        c.fetch_incremental(now=NOW)


def test_missing_id_is_hard_failure():
    broken = row(1)
    broken.pop("id")
    c, _ = connector({1: [broken]})
    with pytest.raises(RuntimeError, match="missing stable id"):
        c.fetch_incremental(now=NOW)


def test_non_list_or_malformed_page_is_hard_failure():
    c1, _ = connector({1: FakeResponse({"items": []})})
    with pytest.raises(RuntimeError, match="non-list JSON"):
        c1.fetch_incremental(now=NOW)

    c2, _ = connector({1: FakeResponse(None, json_error=ValueError("bad json"))})
    with pytest.raises(RuntimeError, match="invalid JSON"):
        c2.fetch_incremental(now=NOW)


def test_http_failure_does_not_return_a_new_cursor():
    c, _ = connector({1: FakeResponse([], status=503)})
    with pytest.raises(requests.HTTPError):
        c.fetch_incremental(now=NOW)


def test_empty_first_page_is_not_accepted_as_complete_national_snapshot():
    c, _ = connector({1: []})
    with pytest.raises(RuntimeError, match="unexpected empty first snapshot page"):
        c.fetch_incremental(now=NOW)


def test_max_pages_is_a_hard_completeness_limit():
    c, _ = connector({1: [row(1), row(2)], 2: [row(3), row(4)]}, max_pages=2)
    with pytest.raises(RuntimeError, match="snapshot exceeds max_pages=2"):
        c.fetch_incremental(now=NOW)


def test_cursor_corruption_and_future_timestamp_fail_closed():
    c, _ = connector({1: [row(1)]})
    with pytest.raises(RuntimeError, match="invalid LT_VPT cursor"):
        c.fetch_incremental(watermark="not-json", now=NOW)

    future = json.dumps({"version": 1, "observed_through": "2026-08-25T12:00:00Z", "tracked": {}})
    with pytest.raises(RuntimeError, match="cursor is in the future"):
        c.fetch_incremental(watermark=future, now=NOW)


def test_page_size_cannot_exceed_live_validated_2000():
    with pytest.raises(ValueError, match="live-validated maximum 2000"):
        LithuaniaVPTSnapshotConnector(session=FakeSession({}), page_size=2001)
