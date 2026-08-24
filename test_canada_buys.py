from datetime import datetime, timezone
import csv
from io import StringIO

import pytest
import requests

from canada_buys import (
    CSV_FIELDS,
    COMPLETE_URL,
    NEW_URL,
    OPEN_URL,
    PUBLIC_SITE,
    CanadaBuysConnector,
    CanadaBuysCursor,
    _parse_csv,
)

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def tender(
    solicitation="W1234-26-0001/A",
    *, reference="cb-123-456", category="*CNST", status="Open",
    deadline="2026-09-08T12:00:00", amendment="000", amendment_date="",
    title="Bridge rehabilitation", notice_url="",
):
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "title-titre-eng": title,
        "referenceNumber-numeroReference": reference,
        "amendmentNumber-numeroModification": amendment,
        "solicitationNumber-numeroSollicitation": solicitation,
        "publicationDate-datePublication": "2026-08-24",
        "tenderClosingDate-appelOffresDateCloture": deadline,
        "amendmentDate-dateModification": amendment_date,
        "tenderStatus-appelOffresStatut-eng": status,
        "procurementCategory-categorieApprovisionnement": category,
        "unspsc": "*72141000\n*72141100",
        "gsin-nibs": "*5133A",
        "noticeType-avisType-eng": "Request for Proposal",
        "procurementMethod-methodeApprovisionnement-eng": "Competitive - Traditional",
        "selectionCriteria-criteresSelection-eng": "Highest Combined Rating of Technical Merit and Price",
        "regionsOfOpportunity-regionAppelOffres-eng": "*Ontario (except NCR)\n*Canada",
        "regionsOfDelivery-regionsLivraison-eng": "*Kingston\n*Ontario (except NCR)",
        "contractingEntityName-nomEntitContractante-eng": "Public Services and Procurement Canada",
        "contractingEntityAddressCity-entiteContractanteAdresseVille-eng": "Ottawa",
        "contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng": "ON",
        "noticeURL-URLavis-eng": notice_url,
        "tenderDescription-descriptionAppelOffres-eng": "Rehabilitate an existing bridge.",
        "expectedContractStartDate-dateDebutContratPrevue": "2026-10-01",
        "expectedContractEndDate-dateFinContratPrevue": "2027-03-31",
    })
    return row


def csv_bytes(rows, *, fields=CSV_FIELDS):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return stream.getvalue().encode("utf-8")


class FakeResponse:
    def __init__(self, content=b"", *, status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)


class FakeSession:
    def __init__(self, responses):
        self.responses = {url: list(values) for url, values in responses.items()}
        self.headers = {}
        self.calls = []

    def get(self, url, *, headers=None, timeout=None):
        self.calls.append((url, dict(headers or {}), timeout))
        values = self.responses.get(url)
        if not values:
            raise AssertionError(f"unexpected GET {url}")
        value = values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def ok(rows, *, etag='"etag"', modified="Mon, 24 Aug 2026 10:20:16 GMT"):
    return FakeResponse(csv_bytes(rows), headers={"ETag": etag, "Last-Modified": modified})


def unchanged():
    return FakeResponse(status=304)


def connector(new=None, open_=None, complete=None):
    responses = {
        NEW_URL: list(new if new is not None else [ok([])]),
        OPEN_URL: list(open_ if open_ is not None else [ok([])]),
    }
    if complete is not None:
        responses[COMPLETE_URL] = list(complete)
    session = FakeSession(responses)
    return CanadaBuysConnector(session=session), session


def decode(value):
    return CanadaBuysCursor.decode(value)


def test_live_schema_contract_is_exactly_67_columns_and_utf8():
    assert len(CSV_FIELDS) == 67
    rows = _parse_csv(csv_bytes([tender(title="Travaux – école")]))
    assert rows[0]["title-titre-eng"] == "Travaux – école"


def test_schema_drift_fails_closed():
    with pytest.raises(RuntimeError, match="schema drift"):
        _parse_csv(csv_bytes([tender()], fields=CSV_FIELDS[:-1]))


def test_invalid_utf8_fails_closed():
    with pytest.raises(RuntimeError, match="not UTF-8"):
        _parse_csv(b"\xff\xfe\xfa")


def test_strict_native_cnst_accepts_multicategory_but_not_keywords():
    works = tender(category="*GD\n*CNST")
    fake_keyword = tender("SVC-1", reference="cb-svc", category="*SRV", title="Construction consulting")
    c, _ = connector(new=[ok([works, fake_keyword])], open_=[ok([works])])
    rows, _ = c.fetch_incremental(now=NOW)
    assert {row["external_id"] for row in rows} == {"W1234-26-0001/A"}


def test_identity_version_deadline_and_no_fabricated_value():
    amended = tender(amendment="004", amendment_date="2026-08-24", notice_url="")
    c, _ = connector(new=[ok([])], open_=[ok([amended])])
    rows, _ = c.fetch_incremental(now=NOW)
    assert len(rows) == 1
    item = rows[0]
    assert item["external_id"] == "W1234-26-0001/A"
    assert item["source_reference"] == "cb-123-456"
    assert item["amendment_number"] == "004"
    assert item["deadline"] == "2026-09-08T17:00:00Z"
    assert item["value"] == ""
    assert item["currency"] == ""
    assert item["url"] == PUBLIC_SITE
    assert item["procurement_categories"] == ["CNST"]
    assert item["unspsc_codes"] == ["72141000", "72141100"]


def test_new_accelerates_discovery_without_duplicate_open_emission():
    value = tender()
    c, _ = connector(new=[ok([value])], open_=[ok([value])])
    rows, cursor = c.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["lifecycle_reason"] == "new_intraday_notice"
    assert set(decode(cursor).tracked) == {"W1234-26-0001/A"}


def test_unchanged_conditional_snapshots_send_validators_and_do_not_reemit():
    value = tender()
    first, _ = connector(new=[ok([])], open_=[ok([value], etag='"open1"', modified="m1")])
    _, watermark = first.fetch_incremental(now=NOW)
    second, session = connector(new=[unchanged()], open_=[unchanged()])
    rows, _ = second.fetch_incremental(watermark=watermark, now=NOW)
    assert rows == []
    calls = {url: headers for url, headers, _ in session.calls}
    assert calls[OPEN_URL]["If-None-Match"] == '"open1"'
    assert calls[OPEN_URL]["If-Modified-Since"] == "m1"


def test_amendment_updates_same_external_identity():
    original = tender(amendment="000")
    first, _ = connector(new=[ok([])], open_=[ok([original])])
    _, watermark = first.fetch_incremental(now=NOW)
    amended = tender(amendment="001", amendment_date="2026-08-25", title="Bridge rehabilitation amended")
    second, _ = connector(new=[unchanged()], open_=[ok([amended])])
    rows, cursor = second.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "W1234-26-0001/A"
    assert rows[0]["amendment_number"] == "001"
    assert len(decode(cursor).tracked) == 1


def test_duplicate_solicitation_in_open_fails_closed():
    c, _ = connector(new=[ok([])], open_=[ok([tender(reference="cb-1"), tender(reference="cb-2")])])
    with pytest.raises(RuntimeError, match="duplicate construction identity in Open"):
        c.fetch_incremental(now=NOW)


def test_open_snapshot_non_open_status_fails_closed():
    c, _ = connector(new=[ok([])], open_=[ok([tender(status="Cancelled")])])
    with pytest.raises(RuntimeError, match="non-open"):
        c.fetch_incremental(now=NOW)


def test_deadline_expires_even_when_open_snapshot_is_http_304():
    value = tender(deadline="2026-08-24T12:00:00")
    first, _ = connector(new=[ok([])], open_=[ok([value])])
    _, watermark = first.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    second, _ = connector(new=[unchanged()], open_=[unchanged()])
    rows, cursor = second.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1
    assert rows[0]["lifecycle_status"] == "expired"
    assert rows[0]["lifecycle_reason"] == "deadline_elapsed_since_unchanged_snapshot"
    assert decode(cursor).tracked == {}


def test_future_disappearance_uses_complete_to_confirm_cancelled():
    value = tender(deadline="2026-09-08T12:00:00")
    first, _ = connector(new=[ok([])], open_=[ok([value])])
    _, watermark = first.fetch_incremental(now=NOW)
    cancelled = tender(status="Cancelled", deadline="2026-09-08T12:00:00", amendment="002")
    second, session = connector(new=[unchanged()], open_=[ok([])], complete=[ok([cancelled])])
    rows, cursor = second.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1
    assert rows[0]["lifecycle_status"] == "cancelled"
    assert rows[0]["lifecycle_reason"] == "complete_file_cancelled"
    assert decode(cursor).tracked == {}
    assert any(call[0] == COMPLETE_URL for call in session.calls)


def test_future_disappearance_without_terminal_proof_is_retained_not_falsely_closed():
    value = tender(deadline="2026-09-08T12:00:00")
    first, _ = connector(new=[ok([])], open_=[ok([value])])
    _, watermark = first.fetch_incremental(now=NOW)
    contradictory_open = tender(status="Open", deadline="2026-09-08T12:00:00")
    second, _ = connector(new=[unchanged()], open_=[ok([])], complete=[ok([contradictory_open])])
    rows, cursor = second.fetch_incremental(watermark=watermark, now=NOW)
    assert rows == []
    assert set(decode(cursor).tracked) == {"W1234-26-0001/A"}


def test_complete_is_not_downloaded_without_ambiguous_missing_ids():
    c, session = connector(new=[ok([])], open_=[ok([tender()])])
    c.fetch_incremental(now=NOW)
    assert [call[0] for call in session.calls] == [NEW_URL, OPEN_URL]


def test_empty_http_200_body_fails_closed():
    c, _ = connector(new=[FakeResponse(b"", status=200)], open_=[ok([])])
    with pytest.raises(RuntimeError, match="empty body"):
        c.fetch_incremental(now=NOW)
