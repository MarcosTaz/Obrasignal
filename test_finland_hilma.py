from datetime import datetime, timezone
import json

import pytest

from finland_hilma import HilmaAVPConnector, HilmaCursor, normalize_notice


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected HILMA API call")
        return self.responses.pop(0)


def _notice(notice_id, *, main_type="ContractNotices", procurement_type="works", published="2026-08-25T08:00:00Z", deadline="2026-09-15T12:00:00Z"):
    return {
        "noticeId": notice_id,
        "titleFi": f"Rakennusurakka {notice_id}",
        "organisationNameFi": "Testikaupunki",
        "organisationNationalRegistrationNumber": "1234567-8",
        "descriptionFi": "Rakennustyöt",
        "cpvCodes": "45000000, 45210000",
        "mainType": main_type,
        "datePublished": published,
        "expirationDate": deadline,
        "nutsCodes": ["FI1B"],
        "procedureType": "open",
        "procurementTypeCode": procurement_type,
        "estimatedValue": 250000,
        "eFormsId": f"ef-{notice_id}",
        "procedureId": 7000 + int(notice_id),
        "procurementDocumentsUrl": "https://example.invalid/docs",
    }


def test_normalize_works_tender_preserves_identity_and_does_not_infer_currency():
    row = normalize_notice(_notice(101), now=NOW)
    assert row["source"] == "FI_HILMA"
    assert row["country"] == "FIN"
    assert row["external_id"] == "101"
    assert row["notice_identifier"] == "ef-101"
    assert row["procedure_reference"] == "7101"
    assert row["signal_type"] == "TENDER"
    assert row["contract_type"] == "works"
    assert row["cpv"] == "45000000"
    assert row["is_actionable"] is True
    assert row["currency"] == ""


def test_non_works_is_rejected_by_publisher_native_taxonomy():
    assert normalize_notice(_notice(102, procurement_type="services"), now=NOW) is None


def test_plan_notice_is_explicit_non_actionable_procurement_plan():
    row = normalize_notice(_notice(103, main_type="PlanNotices", deadline=None), now=NOW)
    assert row["signal_type"] == "PROCUREMENT_PLAN"
    assert row["source_phase"] == "plan"
    assert row["is_actionable"] is False
    assert row["lifecycle_status"] == "planned"


def test_connector_pages_both_tenders_and_plans_and_advances_cursor():
    session = FakeSession([
        FakeResponse({"@odata.count": 2, "value": [_notice(1), _notice(2)]}),
        FakeResponse({"@odata.count": 2, "value": []}),
        FakeResponse({"@odata.count": 1, "value": [_notice(3, main_type="PlanNotices", deadline=None)]}),
    ])
    connector = HilmaAVPConnector(api_key="key", session=session, page_size=2, max_pages=5, overlap_hours=0)
    rows, cursor = connector.fetch_incremental(now=NOW)

    assert [row["external_id"] for row in rows] == ["1", "2", "3"]
    assert [row["signal_type"] for row in rows] == ["TENDER", "TENDER", "PROCUREMENT_PLAN"]
    decoded = HilmaCursor.decode(cursor)
    assert decoded.published_through == "2026-08-25T08:00:00Z"
    assert len(session.calls) == 3
    assert session.calls[0][1]["json"]["skip"] == 0
    assert session.calls[1][1]["json"]["skip"] == 2
    assert "procurementTypeCode eq 'works'" in session.calls[0][1]["json"]["filter"]


def test_incremental_query_uses_overlap_from_previous_cursor():
    session = FakeSession([
        FakeResponse({"value": []}),
        FakeResponse({"value": []}),
    ])
    watermark = HilmaCursor("2026-08-25T10:00:00Z").encode()
    connector = HilmaAVPConnector(api_key="key", session=session, overlap_hours=2)
    connector.fetch_incremental(watermark=watermark, now=NOW)
    assert "datePublished ge 2026-08-25T08:00:00Z" in session.calls[0][1]["json"]["filter"]


def test_duplicate_notice_across_pages_fails_closed():
    session = FakeSession([
        FakeResponse({"value": [_notice(1)]}),
        FakeResponse({"value": [_notice(1)]}),
    ])
    connector = HilmaAVPConnector(api_key="key", session=session, page_size=1, max_pages=3)
    with pytest.raises(RuntimeError, match="duplicate noticeId"):
        connector.fetch_incremental(now=NOW)


def test_invalid_envelope_fails_closed():
    session = FakeSession([FakeResponse({"unexpected": []})])
    connector = HilmaAVPConnector(api_key="key", session=session)
    with pytest.raises(RuntimeError, match="invalid search envelope"):
        connector.fetch_incremental(now=NOW)


def test_api_key_is_required():
    with pytest.raises(RuntimeError, match="HILMA_API_KEY"):
        HilmaAVPConnector(api_key="")
