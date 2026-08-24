from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import pytest

from germany_doe import (
    GermanDOECursor,
    GermanDOEOpenDataConnector,
    SOURCE,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, body=b"", status=200):
        self.body = body
        self.status_code = status
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, size):
        for index in range(0, len(self.body), max(1, size)):
            yield self.body[index:index + size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, by_day):
        self.by_day = dict(by_day)
        self.calls = []

    def get(self, url, *, params, headers, timeout, stream, allow_redirects):
        day = params["pubDay"]
        self.calls.append((url, day, headers.get("Accept")))
        value = self.by_day.get(day, _zip())
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            status, body = value
            return FakeResponse(body, status=status)
        return FakeResponse(value)


def _zip(*entries):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in entries:
            zf.writestr(name, body)
    return buffer.getvalue()


def _company_xml(name="Bauamt Berlin", *, contact=False):
    contact_xml = "<Contact><Name>Private Person</Name><Telephone>+49-secret</Telephone><ElectronicMail>pii@example.invalid</ElectronicMail></Contact>" if contact else ""
    return f"""
    <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
      <efac:Organizations><efac:Organization><efac:Company>
        <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
        <cac:PartyName><cbc:Name>{name}</cbc:Name></cac:PartyName>
        <cac:PostalAddress><cbc:CityName>Berlin</cbc:CityName><cbc:CountrySubentityCode>DE300</cbc:CountrySubentityCode><cac:Country><cbc:IdentificationCode>DEU</cbc:IdentificationCode></cac:Country></cac:PostalAddress>
        {contact_xml}
      </efac:Company></efac:Organization></efac:Organizations>
    </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
    """


def _lot_xml(lot_id="LOT-0001", *, cpv="45234116", deadline="2026-10-20", end_time="11:00:00+02:00", name="Gleisbau", amount="", currency="EUR"):
    deadline_xml = ""
    if deadline:
        deadline_xml = f"""<cac:TenderingProcess><cac:TenderSubmissionDeadlinePeriod><cbc:EndDate>{deadline}+02:00</cbc:EndDate><cbc:EndTime>{end_time}</cbc:EndTime></cac:TenderSubmissionDeadlinePeriod></cac:TenderingProcess>"""
    amount_xml = f'<cbc:EstimatedOverallContractAmount currencyID="{currency}">{amount}</cbc:EstimatedOverallContractAmount>' if amount else ""
    return f"""
      <cac:ProcurementProjectLot>
        <cbc:ID>{lot_id}</cbc:ID><cbc:Name>{name}</cbc:Name>
        <cac:ProcurementProject><cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">{cpv}</cbc:ItemClassificationCode></cac:MainCommodityClassification>{amount_xml}</cac:ProcurementProject>
        {deadline_xml}
      </cac:ProcurementProjectLot>
    """


def _contract_notice(notice_id, folder_id="folder-1", *, kind="works", issue="2026-08-21", issue_time="06:30:00+02:00", lots=None, title="Brückenbau", contact=False):
    lots = lots if lots is not None else [_lot_xml()]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ContractNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac" xmlns:ext="urn:ext" xmlns:efac="urn:efac">
      <cbc:ID>{notice_id}</cbc:ID><cbc:ContractFolderID>{folder_id}</cbc:ContractFolderID><cbc:IssueDate>{issue}+02:00</cbc:IssueDate><cbc:IssueTime>{issue_time}</cbc:IssueTime><cbc:NoticeTypeCode>competition</cbc:NoticeTypeCode>
      {_company_xml(contact=contact)}
      <cac:ContractingParty><cac:Party><cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification></cac:Party></cac:ContractingParty>
      <cac:ProcurementProject><cbc:Name>{title}</cbc:Name><cbc:Description>Öffentliche Bauleistung</cbc:Description><cbc:ProcurementTypeCode>{kind}</cbc:ProcurementTypeCode><cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">45000000</cbc:ItemClassificationCode></cac:MainCommodityClassification><cac:RealizedLocation><cbc:Description>Berlin</cbc:Description><cac:Address><cbc:CountrySubentityCode>DE300</cbc:CountrySubentityCode><cac:Country><cbc:IdentificationCode>DEU</cbc:IdentificationCode></cac:Country></cac:Address></cac:RealizedLocation></cac:ProcurementProject>
      <cac:TenderingProcess><cbc:ProcedureCode>open</cbc:ProcedureCode></cac:TenderingProcess>
      {''.join(lots)}
    </ContractNotice>""".encode()


def _award_notice(notice_id, folder_id="folder-1", *, lot_ids=("LOT-0001",), kind="works", issue="2026-08-22", issue_time="09:00:00+02:00"):
    results = "".join(f"<efac:LotResult><cac:TenderLot><cbc:ID>{lot_id}</cbc:ID></cac:TenderLot></efac:LotResult>" for lot_id in lot_ids)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ContractAwardNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac" xmlns:efac="urn:efac">
      <cbc:ID>{notice_id}</cbc:ID><cbc:ContractFolderID>{folder_id}</cbc:ContractFolderID><cbc:IssueDate>{issue}+02:00</cbc:IssueDate><cbc:IssueTime>{issue_time}</cbc:IssueTime><cbc:NoticeTypeCode>result</cbc:NoticeTypeCode>
      <cac:ProcurementProject><cbc:ProcurementTypeCode>{kind}</cbc:ProcurementTypeCode></cac:ProcurementProject>
      <efac:NoticeResult>{results}</efac:NoticeResult>
    </ContractAwardNotice>""".encode()


def _entry(notice_id, xml, version=1):
    return f"{notice_id}-{version:02d}.xml", xml


def _cursor(completed, tracked=None, closed=None):
    return GermanDOECursor(completed, tracked or {}, closed or {}).encode()


def _state(*, deadline="2026-10-20T09:00:00Z", visible=True, publication_day="2026-08-21"):
    return {
        "external_id": "folder-1::LOT-0001", "procedure_id": "folder-1", "lot_id": "LOT-0001", "lot_count": 1,
        "notice_id": "11111111-1111-1111-1111-111111111111", "file_version": 1, "publication_day": publication_day,
        "notice_type": "competition", "event_kind": "notice", "closed": False, "title": "Old title", "description": "Old",
        "buyer": "Bauamt", "place": "Berlin | DE300 | DEU", "cpv_codes": ["45234116"], "deadline": deadline,
        "value": "", "currency": "", "first_published_at": "2026-08-20T06:00:00Z", "source_updated_at": "2026-08-20T06:00:00Z",
        "url": "https://oeffentlichevergabe.de/ui/de/notices/11111111-1111-1111-1111-111111111111", "procurement_method": "open",
        "was_visible": visible,
    }


def test_works_is_lot_level_and_publication_day_is_not_issue_date():
    notice = "11111111-1111-1111-1111-111111111111"
    lots = [
        _lot_xml("LOT-1", cpv="45234116", deadline="2026-10-20", name="Rail", amount="100", currency="EUR"),
        _lot_xml("LOT-2", cpv="45442110", deadline="2026-09-22", name="Paint", amount="200", currency="EUR"),
    ]
    session = FakeSession({"2026-08-23": _zip(_entry(notice, _contract_notice(notice, issue="2026-08-21", lots=lots)))})
    connector = GermanDOEOpenDataConnector(session=session, initial_lookback_days=1, max_days_per_sync=2, overlap_days=0)
    rows, watermark = connector.fetch_incremental(now=NOW)

    assert {row["external_id"] for row in rows} == {"folder-1::LOT-1", "folder-1::LOT-2"}
    by_id = {row["external_id"]: row for row in rows}
    assert by_id["folder-1::LOT-1"]["cpv"] == "45234116"
    assert by_id["folder-1::LOT-2"]["cpv"] == "45442110"
    assert by_id["folder-1::LOT-1"]["deadline"] == "2026-10-20T09:00:00Z"
    assert by_id["folder-1::LOT-1"]["publication_date"] == "2026-08-23"
    assert by_id["folder-1::LOT-1"]["published_at"].startswith("2026-08-21T")
    assert by_id["folder-1::LOT-1"]["url"].endswith(notice)
    assert by_id["folder-1::LOT-1"]["buyer"] == "Bauamt Berlin"
    assert by_id["folder-1::LOT-1"]["value"] == "100"
    assert by_id["folder-1::LOT-1"]["currency"] == "EUR"
    assert json.loads(watermark)["completed_through"] == "2026-08-23"


def test_nonworks_contract_notice_is_ignored_without_keywords():
    notice = "22222222-2222-2222-2222-222222222222"
    session = FakeSession({"2026-08-23": _zip(_entry(notice, _contract_notice(notice, kind="services", title="Building construction words everywhere")))})
    rows, watermark = GermanDOEOpenDataConnector(session=session, initial_lookback_days=1, overlap_days=0).fetch_incremental(now=NOW)
    assert rows == []
    assert json.loads(watermark)["tracked"] == {}


def test_same_folder_lot_later_contract_notice_updates_deadline_and_identity():
    first = "11111111-1111-1111-1111-111111111111"
    second = "33333333-3333-3333-3333-333333333333"
    session = FakeSession({
        "2026-08-22": _zip(_entry(first, _contract_notice(first, issue="2026-08-20", lots=[_lot_xml(deadline="2026-09-01")]))),
        "2026-08-23": _zip(_entry(second, _contract_notice(second, issue="2026-08-19", lots=[_lot_xml(deadline="2026-10-01")], title="Corrected title"))),
    })
    connector = GermanDOEOpenDataConnector(session=session, initial_lookback_days=2, max_days_per_sync=3, overlap_days=0)
    rows, watermark = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "folder-1::LOT-0001"
    assert rows[0]["deadline"] == "2026-09-30T22:00:00Z"
    assert rows[0]["title"] == "Corrected title"
    assert rows[0]["notice_identifier"] == second
    assert json.loads(watermark)["tracked"]["folder-1::LOT-0001"]["publication_day"] == "2026-08-23"


def test_award_closes_previously_visible_old_tracked_lot():
    award = "44444444-4444-4444-4444-444444444444"
    session = FakeSession({"2026-08-23": _zip(_entry(award, _award_notice(award)))})
    connector = GermanDOEOpenDataConnector(session=session, max_days_per_sync=2, overlap_days=0)
    rows, watermark = connector.fetch_incremental(watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}), now=NOW)
    assert len(rows) == 1
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["is_actionable"] is False
    assert rows[0]["lifecycle_status"] == "awarded_or_completed"
    payload = json.loads(watermark)
    assert payload["tracked"] == {} and payload["closed"] == {}


def test_untracked_award_does_not_create_tender_or_tombstone():
    award = "44444444-4444-4444-4444-444444444444"
    session = FakeSession({"2026-08-23": _zip(_entry(award, _award_notice(award)))})
    rows, watermark = GermanDOEOpenDataConnector(session=session, initial_lookback_days=1, overlap_days=0).fetch_incremental(now=NOW)
    assert rows == []
    assert json.loads(watermark)["tracked"] == {}


def test_missing_deadline_is_kept_pending_and_can_be_restored_by_later_notice():
    first = "11111111-1111-1111-1111-111111111111"
    later = "55555555-5555-5555-5555-555555555555"
    pending = _contract_notice(first, lots=[_lot_xml(deadline="")])
    session1 = FakeSession({"2026-08-23": _zip(_entry(first, pending))})
    connector1 = GermanDOEOpenDataConnector(session=session1, initial_lookback_days=1, overlap_days=0)
    rows1, cursor1 = connector1.fetch_incremental(now=NOW)
    assert rows1 == []
    assert "folder-1::LOT-0001" in json.loads(cursor1)["tracked"]

    next_now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    session2 = FakeSession({"2026-08-24": _zip(_entry(later, _contract_notice(later, issue="2026-08-22", lots=[_lot_xml(deadline="2026-09-30")])))})
    connector2 = GermanDOEOpenDataConnector(session=session2, overlap_days=0)
    rows2, _ = connector2.fetch_incremental(watermark=cursor1, now=next_now)
    assert len(rows2) == 1 and rows2[0]["is_actionable"] is True


def test_visible_deadline_disappearing_emits_one_tombstone_and_keeps_pending():
    notice = "66666666-6666-6666-6666-666666666666"
    state = _state()
    session = FakeSession({"2026-08-23": _zip(_entry(notice, _contract_notice(notice, issue="2026-08-22", lots=[_lot_xml(deadline="")])) )})
    connector = GermanDOEOpenDataConnector(session=session, overlap_days=0)
    rows, cursor = connector.fetch_incremental(watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": state}), now=NOW)
    assert len(rows) == 1 and rows[0]["lifecycle_status"] == "deadline_missing"
    tracked = json.loads(cursor)["tracked"]["folder-1::LOT-0001"]
    assert tracked["was_visible"] is False

    session2 = FakeSession({"2026-08-23": _zip()})
    connector2 = GermanDOEOpenDataConnector(session=session2, overlap_days=1)
    rows2, _ = connector2.fetch_incremental(watermark=cursor, now=NOW)
    assert rows2 == []


def test_elapsed_deadline_closes_visible_target_without_surviving():
    session = FakeSession({"2026-08-23": _zip()})
    connector = GermanDOEOpenDataConnector(session=session, overlap_days=0)
    old = _state(deadline="2026-08-23T00:00:00Z", visible=True)
    rows, cursor = connector.fetch_incremental(watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": old}), now=NOW)
    assert len(rows) == 1 and rows[0]["lifecycle_status"] == "deadline_elapsed"
    assert json.loads(cursor)["tracked"] == {}


def test_long_initial_catchup_emits_nothing_until_target_day_reached():
    notice = "11111111-1111-1111-1111-111111111111"
    by_day = {"2026-08-19": _zip(_entry(notice, _contract_notice(notice, issue="2026-08-18")))}
    connector = GermanDOEOpenDataConnector(session=FakeSession(by_day), initial_lookback_days=5, max_days_per_sync=2, overlap_days=0)
    rows1, cursor1 = connector.fetch_incremental(now=NOW)
    assert rows1 == []
    assert json.loads(cursor1)["completed_through"] == "2026-08-20"
    assert json.loads(cursor1)["tracked"]["folder-1::LOT-0001"]["was_visible"] is False

    connector2 = GermanDOEOpenDataConnector(session=FakeSession({}), max_days_per_sync=2, overlap_days=0)
    rows2, cursor2 = connector2.fetch_incremental(watermark=cursor1, now=NOW)
    assert rows2 == []
    assert json.loads(cursor2)["completed_through"] == "2026-08-22"

    connector3 = GermanDOEOpenDataConnector(session=FakeSession({}), max_days_per_sync=2, overlap_days=0)
    rows3, cursor3 = connector3.fetch_incremental(watermark=cursor2, now=NOW)
    assert len(rows3) == 1 and rows3[0]["is_actionable"] is True
    assert json.loads(cursor3)["completed_through"] == "2026-08-23"


def test_catchup_preserves_visible_closure_until_final_day():
    state = _state(visible=True)
    award = "44444444-4444-4444-4444-444444444444"
    connector1 = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-21": _zip(_entry(award, _award_notice(award)))}), max_days_per_sync=1, overlap_days=0)
    rows1, cursor1 = connector1.fetch_incremental(watermark=_cursor("2026-08-20", {"folder-1::LOT-0001": state}), now=NOW)
    assert rows1 == []
    assert "folder-1::LOT-0001" in json.loads(cursor1)["closed"]

    connector2 = GermanDOEOpenDataConnector(session=FakeSession({}), max_days_per_sync=5, overlap_days=0)
    rows2, cursor2 = connector2.fetch_incremental(watermark=cursor1, now=NOW)
    assert len(rows2) == 1 and rows2[0]["lifecycle_status"] == "awarded_or_completed"
    assert json.loads(cursor2)["closed"] == {}


def test_cursor_future_corrupt_and_invalid_state_fail_closed():
    connector = GermanDOEOpenDataConnector(session=FakeSession({}))
    with pytest.raises(RuntimeError, match="cursor JSON"):
        connector.fetch_incremental(watermark="{not-json", now=NOW)
    with pytest.raises(RuntimeError, match="cursor is ahead"):
        connector.fetch_incremental(watermark=_cursor("2026-08-24"), now=NOW)
    bad = json.dumps({"completed_through": "2026-08-22", "tracked": [], "closed": {}})
    with pytest.raises(RuntimeError, match="cursor state"):
        connector.fetch_incremental(watermark=bad, now=NOW)


def test_overlap_is_bounded_below_day_budget_so_progress_cannot_stall():
    connector = GermanDOEOpenDataConnector(session=FakeSession({}), initial_lookback_days=5, max_days_per_sync=2, overlap_days=10)
    rows1, cursor1 = connector.fetch_incremental(now=NOW)
    completed1 = json.loads(cursor1)["completed_through"]
    connector2 = GermanDOEOpenDataConnector(session=FakeSession({}), max_days_per_sync=2, overlap_days=10)
    rows2, cursor2 = connector2.fetch_incremental(watermark=cursor1, now=NOW)
    completed2 = json.loads(cursor2)["completed_through"]
    assert rows1 == rows2 == []
    assert completed2 > completed1


def test_duplicate_zip_names_are_rejected():
    notice = "11111111-1111-1111-1111-111111111111"
    body = _zip(_entry(notice, _contract_notice(notice)), _entry(notice, _contract_notice(notice)))
    connector = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0)
    with pytest.raises(RuntimeError, match="duplicate filenames"):
        connector.fetch_incremental(now=NOW)


def test_non_zip_and_malformed_zip_fail_closed():
    for body in (b"not zip", b"PKbroken"):
        connector = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0)
        with pytest.raises(RuntimeError):
            connector.fetch_incremental(now=NOW)


def test_archive_entry_and_uncompressed_hard_limits():
    notice = "11111111-1111-1111-1111-111111111111"
    body = _zip(_entry(notice, _contract_notice(notice)))
    with pytest.raises(RuntimeError, match="max_entry_bytes"):
        GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0, max_entry_bytes=1024).fetch_incremental(now=NOW)
    with pytest.raises(RuntimeError, match="max_uncompressed_bytes"):
        GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0, max_entry_bytes=100000, max_uncompressed_bytes=1500).fetch_incremental(now=NOW)


def test_archive_byte_limit_stops_transport():
    notice = "11111111-1111-1111-1111-111111111111"
    body = _zip(_entry(notice, _contract_notice(notice)))
    connector = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0, max_archive_bytes=1024)
    with pytest.raises(RuntimeError, match="max_archive_bytes"):
        connector.fetch_incremental(now=NOW)


def test_malformed_xml_and_filename_identity_mismatch_fail():
    good_name = "11111111-1111-1111-1111-111111111111-01.xml"
    with pytest.raises(RuntimeError, match="malformed eForms XML"):
        GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": _zip((good_name, b"<broken"))}), initial_lookback_days=1, overlap_days=0).fetch_incremental(now=NOW)
    wrong_root = _contract_notice("22222222-2222-2222-2222-222222222222")
    with pytest.raises(RuntimeError, match="filename/root"):
        GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": _zip((good_name, wrong_root))}), initial_lookback_days=1, overlap_days=0).fetch_incremental(now=NOW)


def test_unknown_eforms_family_is_ignored_without_text_heuristics():
    unknown = b'<?xml version="1.0"?><PriorInformationNotice><ID>anything</ID><Text>works construction</Text></PriorInformationNotice>'
    name = "11111111-1111-1111-1111-111111111111-01.xml"
    rows, _ = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": _zip((name, unknown))}), initial_lookback_days=1, overlap_days=0).fetch_incremental(now=NOW)
    assert rows == []


def test_raw_xml_and_contact_pii_are_not_persisted():
    notice = "11111111-1111-1111-1111-111111111111"
    body = _zip(_entry(notice, _contract_notice(notice, contact=True)))
    rows, _ = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0).fetch_incremental(now=NOW)
    assert len(rows) == 1
    serialized = json.dumps(rows[0], ensure_ascii=False)
    assert "pii@example.invalid" not in serialized
    assert "+49-secret" not in serialized
    assert "<ContractNotice" not in serialized
    assert rows[0]["reuse_license"] == "CC0-1.0"
    assert rows[0]["source"] == SOURCE


def test_award_for_tracked_folder_without_lot_identity_fails_closed():
    award = "44444444-4444-4444-4444-444444444444"
    body = _award_notice(award, lot_ids=())
    connector = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": _zip(_entry(award, body))}), overlap_days=0)
    with pytest.raises(RuntimeError, match="no lot identities"):
        connector.fetch_incremental(watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}), now=NOW)
