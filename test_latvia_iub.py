from datetime import date, datetime, timezone

from official_json_bulk_adapter import DailyBulkCursor
from latvia_iub import (
    LV_IUB_LICENSE,
    build_iub_connector,
    iub_daily_url,
    normalize_iub_notice,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.content = b"[]" if payload == [] else b"{json}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
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


def _lot(*, lot_id="533285", sequence="1", deadline_date="22/09/2026", deadline_time="10:00", value="240356.40"):
    return {
        "id": lot_id,
        "name": "Bridge rehabilitation works",
        "description": "Rehabilitation of an existing public structure",
        "sequenceNumber": sequence,
        "additionalInformation": {"estimatedValue": value},
        "tenderingTerms": {"isEuFunded": True},
        "place": {
            "placePerformanceCountryCode": "LVA",
            "placePerformanceCountrySubCode": "LV009",
            "placePerformanceRegionDescription": "Bauska, Latvia",
        },
        "tenderingProcess": {
            "reviewDeadlineDate": "15/09/2026",
            "reviewDeadlineDescription": "Complaint/review deadline",
            "deadlineReceiptTendersEndDate": deadline_date,
            "deadlineReceiptTendersEndTime": deadline_time,
        },
    }


def _notice(*, form_type="competition", lot=None, identifier="notice-current", cloned_from=None):
    return {
        "identifier": identifier,
        "procurementProcedureIdentifier": "procedure-123",
        "formType": form_type,
        "noticeType": "pil-contract" if form_type == "competition" else "pil-prior-information",
        "name": "Bridge rehabilitation works",
        "cpvType": "45221111-3",
        "procurementProject": {
            "description": "Bridge rehabilitation",
            "mainNatureType": "works",
            "procurementIdentifier": "LV-ROAD-2026-01",
        },
        "tenderingProcess": {
            "documentsURL": "https://www.eis.gov.lv/EKEIS/Supplier/Procurement/180083",
            "procedureType": "open",
            "reviewDeadlineDescription": "This is not the tender submission deadline",
        },
        "tenderingTerms": {
            "submissionURL": "https://www.eis.gov.lv/EKEIS/Supplier/Procurement/180083",
        },
        "organizationData": {
            "name": "Bauskas novada pašvaldība",
            "identifier": "90009116223",
            "city": "Bauska",
            "nutsCode": "LV009",
        },
        "contactPoint": {
            "name": "Iepirkumu nodaļa",
            "electronicMail": "procurement@example.invalid",
        },
        "lots": [lot or _lot()],
        "clonedFrom": cloned_from,
    }


def test_daily_url_matches_official_iub_physical_naming_contract():
    assert iub_daily_url(date(2026, 8, 23)) == "https://open.iub.gov.lv/data/notice/2026/08/23-08-2026.json"


def test_competition_is_normalized_per_lot_using_submission_deadline_not_review_deadline():
    rows = normalize_iub_notice(
        _notice(),
        publication_day=date(2026, 8, 23),
        now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "LV_IUB"
    assert row["country"] == "LVA"
    assert row["external_id"] == "procedure-123:lot:1"
    assert row["deadline"] == "2026-09-22T07:00:00Z"
    assert "15/09/2026" not in row["deadline"]
    assert row["cpv"] == "45221111"
    assert row["taxonomy"] == "CPV"
    assert row["value"] == "240356.40"
    assert row["currency"] == ""
    assert row["contract_type"] == "works"
    assert row["place"].startswith("Bauska, Latvia")
    assert row["url"].endswith("/Procurement/180083")
    assert row["license"] == LV_IUB_LICENSE
    assert row["signal_type"] == "TENDER"


def test_republication_keeps_canonical_lot_identity_when_native_lot_id_changes():
    old_notice = _notice(identifier="notice-old", lot=_lot(lot_id="528044", sequence="1", deadline_date="03/09/2026"))
    current_notice = _notice(
        identifier="notice-new",
        lot=_lot(lot_id="533257", sequence="1", deadline_date="14/09/2026", deadline_time="09:00"),
        cloned_from=old_notice,
    )

    old_row = normalize_iub_notice(
        old_notice,
        publication_day=date(2026, 8, 10),
        now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc),
    )[0]
    current_row = normalize_iub_notice(
        current_notice,
        publication_day=date(2026, 8, 23),
        now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc),
    )[0]

    assert old_row["lot_id"] == "528044"
    assert current_row["lot_id"] == "533257"
    assert old_row["external_id"] == current_row["external_id"] == "procedure-123:lot:1"
    assert current_row["source_reference"] == "notice-new"
    assert current_row["is_republication"] is True
    assert current_row["cloned_from_identifier"] == "notice-old"
    assert current_row["deadline"] == "2026-09-14T06:00:00Z"


def test_planning_results_and_expired_competitions_do_not_leak_into_tender_runtime():
    now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    assert normalize_iub_notice(_notice(form_type="planning"), publication_day=date(2026, 8, 23), now=now) == []
    assert normalize_iub_notice(_notice(form_type="result"), publication_day=date(2026, 8, 23), now=now) == []
    assert normalize_iub_notice(
        _notice(lot=_lot(deadline_date="24/08/2026", deadline_time="12:00")),
        publication_day=date(2026, 8, 23),
        now=now,
    ) == []


def test_multi_lot_notice_emits_only_open_lots_with_stable_sequence_keys():
    notice = _notice()
    notice["lots"] = [
        _lot(lot_id="100", sequence="1", deadline_date="25/08/2026", deadline_time="12:00"),
        _lot(lot_id="101", sequence="2", deadline_date="23/08/2026", deadline_time="12:00"),
        _lot(lot_id="102", sequence="3", deadline_date="30/08/2026", deadline_time="09:30"),
    ]
    rows = normalize_iub_notice(
        notice,
        publication_day=date(2026, 8, 23),
        now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
    )
    assert [row["external_id"] for row in rows] == ["procedure-123:lot:1", "procedure-123:lot:3"]


def test_connector_uses_one_day_publication_lag_and_advances_daily_cursor():
    session = FakeSession([FakeResponse([_notice()])])
    connector = build_iub_connector(session=session)
    connector.config = type(connector.config)(
        **{
            **connector.config.__dict__,
            "initial_lookback_days": 0,
            "overlap_days": 0,
            "max_days_per_sync": 1,
        }
    )

    rows, cursor = connector.fetch_incremental(now=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))

    assert len(rows) == 1
    assert session.calls[0]["url"].endswith("/2026/08/23-08-2026.json")
    assert DailyBulkCursor.decode(cursor).completed_through == "2026-08-23"
