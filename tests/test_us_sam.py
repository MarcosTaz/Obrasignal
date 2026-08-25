import io
from datetime import datetime, timedelta, timezone

import pytest

from us_sam import CSV_FIELDS, SAMCursor, SAMGovConnector, SOURCE, _observation


class FakeResponse:
    def __init__(self, body=b"", status=200, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.raw = io.BytesIO(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def csv_bytes(rows):
    out = io.StringIO(newline="")
    import csv
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})
    return out.getvalue().encode("utf-8")


def construction_row(**overrides):
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    row = {
        "NoticeId": "abc123",
        "Title": "Federal building renovation",
        "Sol#": "W9123-26-R-0001",
        "Department/Ind.Agency": "DEPARTMENT OF THE ARMY",
        "Sub-Tier": "US ARMY CORPS OF ENGINEERS",
        "Office": "USACE OFFICE",
        "PostedDate": "2026-08-24",
        "Type": "Solicitation",
        "BaseType": "Presolicitation",
        "ArchiveType": "auto15",
        "ArchiveDate": "2026-09-30",
        "ResponseDeadLine": future,
        "NaicsCode": "236220",
        "ClassificationCode": "Z2AA",
        "PopCity": "Norfolk",
        "PopState": "VA",
        "PopCountry": "USA",
        "Active": "Yes",
        "Award$": "999999999",
        "PrimaryContactFullname": "Jane Doe",
        "PrimaryContactEmail": "jane@example.mil",
        "Link": "https://sam.gov/opp/abc123/view",
        "Description": "Renovation works. Magnitude not normalized by ObraSignal.",
    }
    row.update(overrides)
    return row


def test_publisher_naics_23_is_the_construction_gate_and_award_value_is_not_tender_value():
    item = _observation(construction_row())
    assert item["external_id"] == "abc123"
    assert item["taxonomy"] == "NAICS"
    assert item["category_code"] == "236220"
    assert item["contract_type"] == "works"
    assert item["value"] == ""
    assert item["currency"] == ""
    assert item["procedure_reference"] == "W9123-26-R-0001"
    assert item["is_actionable"] is True


def test_non_construction_never_passes_observation_boundary():
    with pytest.raises(RuntimeError, match="non-construction"):
        _observation(construction_row(NaicsCode="541330"))


def test_award_notice_is_retained_only_if_explicitly_observed_but_not_actionable():
    item = _observation(construction_row(Type="Award Notice"))
    assert item["is_actionable"] is False
    assert item["notice_type"] == "Award Notice"


def test_bulk_fetch_filters_to_construction_and_advances_etag_cursor():
    body = csv_bytes([
        construction_row(),
        construction_row(NoticeId="other", NaicsCode="541330", Title="Engineering services"),
    ])
    session = FakeSession(FakeResponse(body, headers={"ETag": '"etag-1"', "Last-Modified": "Mon, 24 Aug 2026 03:30:33 GMT"}))
    rows, cursor = SAMGovConnector(session=session).fetch()
    assert [row["external_id"] for row in rows] == ["abc123"]
    decoded = SAMCursor.decode(cursor)
    assert decoded.etag == '"etag-1"'
    assert decoded.last_modified.startswith("Mon, 24 Aug 2026")


def test_conditional_304_returns_no_observations_and_preserves_cursor():
    old = SAMCursor(etag='"etag-1"', last_modified="Mon, 24 Aug 2026 03:30:33 GMT").encode()
    session = FakeSession(FakeResponse(status=304))
    rows, cursor = SAMGovConnector(session=session).fetch(watermark=old)
    assert rows == []
    assert cursor == old
    headers = session.calls[0][1]["headers"]
    assert headers["If-None-Match"] == '"etag-1"'
    assert headers["If-Modified-Since"].startswith("Mon, 24 Aug 2026")


def test_schema_drift_fails_closed_without_cursor_advance():
    malformed = b"NoticeId,Title,NaicsCode\nabc,Works,236220\n"
    with pytest.raises(RuntimeError, match="schema drift"):
        SAMGovConnector(session=FakeSession(FakeResponse(malformed))).fetch()


def test_missing_notice_identity_fails_closed():
    body = csv_bytes([construction_row(NoticeId="")])
    with pytest.raises(RuntimeError, match="missing NoticeId"):
        SAMGovConnector(session=FakeSession(FakeResponse(body))).fetch()
