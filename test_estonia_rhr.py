from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pytest

from estonia_rhr import EERHRCursor, EstoniaRHRConnector, _notice_events, _periods

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def notice_xml(*, folder="folder-1", notice_id="notice-1", issue_date="2026-08-20+03:00", project_type="works", deadline_date="2026-08-28+03:00", deadline_time="12:00:00.000+03:00", lot_id="LOT-0000", cpv="45213000"):
    return f"""<ContractNotice>
    <UBLExtensions><UBLExtension><ExtensionContent><EformsExtension><Organizations>
      <Organization><Company><PartyIdentification><ID>ORG-0001</ID></PartyIdentification><PartyName><Name>Tallinna Testasutus</Name></PartyName><PostalAddress><CityName>Tallinn</CityName><CountrySubentityCode>EE001</CountrySubentityCode><Country><IdentificationCode>EST</IdentificationCode></Country></PostalAddress></Company></Organization>
    </Organizations></EformsExtension></ExtensionContent></UBLExtension></UBLExtensions>
    <ID>{notice_id}</ID><ContractFolderID>{folder}</ContractFolderID><IssueDate>{issue_date}</IssueDate><IssueTime>10:30:00.000+03:00</IssueTime><VersionID>01</VersionID><NoticeTypeCode>cn-standard</NoticeTypeCode>
    <ContractingParty><Party><PartyIdentification><ID>ORG-0001</ID></PartyIdentification></Party></ContractingParty>
    <TenderingProcess><ProcedureCode>open</ProcedureCode></TenderingProcess>
    <ProcurementProject><ID>313158-0000</ID><Name>Kalakäitlemise tootmishoone ehitamine</Name><Description>Projektikirjeldus</Description><ProcurementTypeCode>{project_type}</ProcurementTypeCode><EstimatedOverallContractAmount currencyID="EUR">125000.00</EstimatedOverallContractAmount><MainCommodityClassification><ItemClassificationCode listName="cpv">{cpv}</ItemClassificationCode></MainCommodityClassification><RealizedLocation><Description>Tallinn ehitusobjekt</Description><Address><CountrySubentityCode>EE001</CountrySubentityCode><Country><IdentificationCode>EST</IdentificationCode></Country></Address></RealizedLocation></ProcurementProject>
    <ProcurementProjectLot><ID>{lot_id}</ID><MainCommodityClassification><ItemClassificationCode listName="cpv">{cpv}</ItemClassificationCode></MainCommodityClassification><TenderingProcess><TenderSubmissionDeadlinePeriod><EndDate>{deadline_date}</EndDate><EndTime>{deadline_time}</EndTime></TenderSubmissionDeadlinePeriod></TenderingProcess></ProcurementProjectLot>
    <AdditionalDocumentReference><Attachment><ExternalReference><URI>https://riigihanked.riik.ee/rhr-web/#/procurement/10570524/documents?group=B</URI></ExternalReference></Attachment></AdditionalDocumentReference>
    </ContractNotice>"""


def award_xml(*, folder="folder-1", notice_id="award-1", lot_id="LOT-0000"):
    return f"""<ContractAwardNotice><ID>{notice_id}</ID><ContractFolderID>{folder}</ContractFolderID><IssueDate>2026-08-23+03:00</IssueDate><IssueTime>09:00:00.000+03:00</IssueTime><NoticeTypeCode>can-standard</NoticeTypeCode><NoticeResult><LotResult><ID>RES-1</ID><TenderResultCode>selec-w</TenderResultCode><TenderLot><ID>{lot_id}</ID></TenderLot></LotResult></NoticeResult><ProcurementProject><ID>313158-0000</ID><Name>Ehitus</Name><ProcurementTypeCode>works</ProcurementTypeCode></ProcurementProject><ProcurementProjectLot><ID>{lot_id}</ID></ProcurementProjectLot></ContractAwardNotice>"""


def open_data(*rows):
    return ("<OPEN-DATA>" + "".join(rows) + "</OPEN-DATA>").encode()


class Response:
    def __init__(self, payload, content_length=None):
        self.payload = payload
        self.status_code = 200
        self.headers = {"content-length": str(len(payload) if content_length is None else content_length)}
    def raise_for_status(self):
        return None
    def iter_content(self, chunk_size=131072):
        for i in range(0, len(self.payload), chunk_size):
            yield self.payload[i:i + chunk_size]
    def close(self):
        return None


class Session:
    def __init__(self, notices, awards=None, content_length=None):
        self.notices = notices
        self.awards = awards if awards is not None else open_data()
        self.content_length = content_length
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(url)
        return Response(self.awards if "/notice_award/" in url else self.notices, self.content_length)


def test_notice_parser_uses_native_works_gate_identity_cpv_and_timezone():
    event = _notice_events(ET.fromstring(notice_xml()))[0]
    assert event["external_id"] == "folder-1::LOT-0000"
    assert event["buyer"] == "Tallinna Testasutus"
    assert event["cpv_codes"] == ["45213000"]
    assert event["deadline"] == "2026-08-28T09:00:00Z"
    assert event["source_updated_at"] == "2026-08-20T07:30:00Z"
    assert event["value"] == "125000.00" and event["currency"] == "EUR"
    assert "Tallinn ehitusobjekt" in event["place"]
    assert _notice_events(ET.fromstring(notice_xml(project_type="services"))) == []


def test_republication_same_folder_uses_issue_timestamp_not_version_id():
    older = notice_xml(notice_id="old", issue_date="2026-08-20+03:00", deadline_date="2026-08-26+03:00")
    newer = notice_xml(notice_id="new", issue_date="2026-08-22+03:00", deadline_date="2026-09-04+03:00")
    connector = EstoniaRHRConnector(session=Session(open_data(older, newer)), initial_months=1, overlap_months=0)
    rows, cursor = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["source_reference"] == "new"
    assert rows[0]["deadline"] == "2026-09-04T09:00:00Z"
    state = EERHRCursor.decode(cursor).tracked["folder-1::LOT-0000"]
    assert state["first_published_at"] == "2026-08-20T07:30:00Z"


def test_award_closes_visible_lot_and_never_emits_initial_intermediate_state():
    seed = EstoniaRHRConnector(session=Session(open_data(notice_xml())), initial_months=1, overlap_months=0)
    rows, watermark = seed.fetch_incremental(now=NOW)
    assert len(rows) == 1

    closing = EstoniaRHRConnector(session=Session(open_data(notice_xml()), open_data(award_xml())), initial_months=1, overlap_months=0)
    rows, cursor = closing.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1 and rows[0]["is_actionable"] is False
    assert rows[0]["lifecycle_status"] == "result_published"
    assert rows[0]["_lifecycle_only"] is True
    assert EERHRCursor.decode(cursor).tracked == {}

    initial_closed = EstoniaRHRConnector(session=Session(open_data(notice_xml()), open_data(award_xml())), initial_months=1, overlap_months=0)
    rows, cursor = initial_closed.fetch_incremental(now=NOW)
    assert rows == [] and EERHRCursor.decode(cursor).tracked == {}


def test_elapsed_tracked_deadline_emits_tombstone_once():
    payload = open_data(notice_xml(deadline_date="2026-08-21+03:00"))
    early = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)
    seed = EstoniaRHRConnector(session=Session(payload), initial_months=1, overlap_months=0)
    rows, watermark = seed.fetch_incremental(now=early)
    assert len(rows) == 1
    later = EstoniaRHRConnector(session=Session(payload), initial_months=1, overlap_months=0)
    rows, cursor = later.fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1 and rows[0]["lifecycle_status"] == "deadline_elapsed"
    assert EERHRCursor.decode(cursor).tracked == {}


def test_cursor_sync_reprocesses_current_and_previous_month():
    payload = open_data(notice_xml())
    seed = EstoniaRHRConnector(session=Session(payload), initial_months=1, overlap_months=0)
    _rows, watermark = seed.fetch_incremental(now=NOW)
    session = Session(payload)
    EstoniaRHRConnector(session=session, overlap_months=1).fetch_incremental(watermark=watermark, now=NOW)
    assert any("/2026/month/7/xml" in url for url in session.calls)
    assert any("/2026/month/8/xml" in url for url in session.calls)
    assert len(session.calls) == 4


def test_initial_three_months_and_tallinn_calendar_boundary():
    assert _periods(NOW, 3) == [(2026, 6), (2026, 7), (2026, 8)]
    boundary = datetime(2026, 8, 31, 21, 30, tzinfo=timezone.utc)
    assert _periods(boundary, 2) == [(2026, 8), (2026, 9)]


def test_invalid_cursor_and_resource_limit_fail_closed():
    with pytest.raises(RuntimeError, match="invalid EE_RHR cursor"):
        EERHRCursor.decode("not-json")
    connector = EstoniaRHRConnector(session=Session(open_data(notice_xml()), content_length=999999), initial_months=1, overlap_months=0, max_resource_bytes=1000)
    with pytest.raises(RuntimeError, match="max_resource_bytes=.*cursor not advanced"):
        connector.fetch_incremental(now=NOW)
