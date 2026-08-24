from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import pytest

from germany_doe import GermanDOECursor, GermanDOEOpenDataConnector, SOURCE

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, body=b"", status=200):
        self.body, self.status_code, self.closed = body, status, False

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
        self.by_day, self.calls = dict(by_day), []

    def get(self, url, *, params, headers, timeout, stream, allow_redirects):
        day = params["pubDay"]
        self.calls.append((url, day, headers.get("Accept")))
        value = self.by_day.get(day, _zip())
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            return FakeResponse(value[1], status=value[0])
        return FakeResponse(value)


def _zip(*entries):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in entries:
            zf.writestr(name, body)
    return buf.getvalue()


def _uuid(index):
    return f"00000000-0000-0000-0000-{int(index):012d}"


def _company_xml(contact=False):
    pii = "<Contact><Telephone>+49-secret</Telephone><ElectronicMail>pii@example.invalid</ElectronicMail></Contact>" if contact else ""
    return f"""
    <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
      <efac:Organizations><efac:Organization><efac:Company>
        <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
        <cac:PartyName><cbc:Name>Bauamt Berlin</cbc:Name></cac:PartyName>
        <cac:PostalAddress><cbc:CityName>Berlin</cbc:CityName><cbc:CountrySubentityCode>DE300</cbc:CountrySubentityCode><cac:Country><cbc:IdentificationCode>DEU</cbc:IdentificationCode></cac:Country></cac:PostalAddress>
        {pii}
      </efac:Company></efac:Organization></efac:Organizations>
    </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>"""


def _lot(
    lot_id="LOT-0001",
    *,
    cpv="45234116",
    deadline="2026-10-20",
    time="11:00:00+02:00",
    name="Gleisbau",
    amount="",
    scheme="",
):
    period = "" if not deadline else (
        f"<cac:TenderingProcess><cac:TenderSubmissionDeadlinePeriod>"
        f"<cbc:EndDate>{deadline}+02:00</cbc:EndDate><cbc:EndTime>{time}</cbc:EndTime>"
        f"</cac:TenderSubmissionDeadlinePeriod></cac:TenderingProcess>"
    )
    value = "" if not amount else f'<cbc:EstimatedOverallContractAmount currencyID="EUR">{amount}</cbc:EstimatedOverallContractAmount>'
    attr = f' schemeName="{scheme}"' if scheme else ""
    return (
        f"<cac:ProcurementProjectLot><cbc:ID{attr}>{lot_id}</cbc:ID><cbc:Name>{name}</cbc:Name>"
        f"<cac:ProcurementProject><cac:MainCommodityClassification>"
        f'<cbc:ItemClassificationCode listName="cpv">{cpv}</cbc:ItemClassificationCode>'
        f"</cac:MainCommodityClassification>{value}</cac:ProcurementProject>{period}</cac:ProcurementProjectLot>"
    )


def _notice(notice_id, *, folder="folder-1", kind="works", issue="2026-08-21", lots=None, title="Brückenbau", contact=False):
    lots = [_lot()] if lots is None else lots
    return f"""<?xml version="1.0"?><ContractNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac" xmlns:ext="urn:ext" xmlns:efac="urn:efac">
    <cbc:ID>{notice_id}</cbc:ID><cbc:ContractFolderID>{folder}</cbc:ContractFolderID><cbc:IssueDate>{issue}+02:00</cbc:IssueDate><cbc:IssueTime>06:30:00+02:00</cbc:IssueTime><cbc:NoticeTypeCode>competition</cbc:NoticeTypeCode>
    {_company_xml(contact)}
    <cac:ContractingParty><cac:Party><cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification></cac:Party></cac:ContractingParty>
    <cac:ProcurementProject><cbc:Name>{title}</cbc:Name><cbc:Description>Öffentliche Bauleistung</cbc:Description><cbc:ProcurementTypeCode>{kind}</cbc:ProcurementTypeCode><cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">45000000</cbc:ItemClassificationCode></cac:MainCommodityClassification><cac:RealizedLocation><cbc:Description>Berlin</cbc:Description><cac:Address><cbc:CountrySubentityCode>DE300</cbc:CountrySubentityCode><cac:Country><cbc:IdentificationCode>DEU</cbc:IdentificationCode></cac:Country></cac:Address></cac:RealizedLocation></cac:ProcurementProject>
    <cac:TenderingProcess><cbc:ProcedureCode>open</cbc:ProcedureCode></cac:TenderingProcess>{''.join(lots)}</ContractNotice>""".encode()


def _award(notice_id, *, folder="folder-1", lot_ids=("LOT-0001",), kind="works", status="selec-w", include_status=True):
    result_code = (
        f'<cbc:TenderResultCode listName="winner-selection-status">{status}</cbc:TenderResultCode>'
        if include_status else ""
    )
    results = "".join(
        f"<efac:LotResult>{result_code}<cac:TenderLot><cbc:ID schemeName=\"Lot\">{lot}</cbc:ID></cac:TenderLot></efac:LotResult>"
        for lot in lot_ids
    )
    return f"""<?xml version="1.0"?><ContractAwardNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac" xmlns:efac="urn:efac"><cbc:ID>{notice_id}</cbc:ID><cbc:ContractFolderID>{folder}</cbc:ContractFolderID><cbc:IssueDate>2026-08-22+02:00</cbc:IssueDate><cbc:IssueTime>09:00:00+02:00</cbc:IssueTime><cbc:NoticeTypeCode>result</cbc:NoticeTypeCode><cac:ProcurementProject><cbc:ProcurementTypeCode>{kind}</cbc:ProcurementTypeCode></cac:ProcurementProject><efac:NoticeResult>{results}</efac:NoticeResult></ContractAwardNotice>""".encode()


def _entry(notice_id, body, version=1):
    return f"{notice_id}-{version:02d}.xml", body


def _cursor(completed, tracked=None, closed=None):
    return GermanDOECursor(completed, tracked or {}, closed or {}).encode()


def _state(deadline="2026-10-20T09:00:00Z", visible=True):
    return {
        "external_id": "folder-1::LOT-0001",
        "procedure_id": "folder-1",
        "lot_id": "LOT-0001",
        "lot_count": 1,
        "notice_id": _uuid(1),
        "file_version": 1,
        "publication_day": "2026-08-21",
        "notice_type": "competition",
        "event_kind": "notice",
        "closed": False,
        "title": "Old",
        "description": "Old",
        "buyer": "Bauamt",
        "place": "Berlin",
        "cpv_codes": ["45234116"],
        "deadline": deadline,
        "value": "",
        "currency": "",
        "first_published_at": "2026-08-20T04:00:00Z",
        "source_updated_at": "2026-08-20T04:00:00Z",
        "url": "https://oeffentlichevergabe.de/ui/de/notices/x",
        "procurement_method": "open",
        "was_visible": visible,
    }


def _archive(count):
    return _zip(*[
        _entry(_uuid(i), _notice(_uuid(i), folder=f"folder-{i}", title=f"Works {i} unique payload {i * 7919}"))
        for i in range(1, count + 1)
    ])


def test_works_are_lot_level_and_pubday_not_issue_date():
    nid = _uuid(1)
    lots = [
        _lot("LOT-A", cpv="45234116", deadline="2026-10-20", amount="100"),
        _lot("LOT-B", cpv="45442110", deadline="2026-09-22", amount="200"),
    ]
    connector = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(nid, _notice(nid, issue="2026-08-21", lots=lots)))}),
        initial_lookback_days=1,
        overlap_days=0,
    )
    rows, cursor = connector.fetch_incremental(now=NOW)
    assert {r["external_id"] for r in rows} == {"folder-1::LOT-A", "folder-1::LOT-B"}
    a = {r["external_id"]: r for r in rows}["folder-1::LOT-A"]
    assert a["cpv"] == "45234116" and a["deadline"] == "2026-10-20T09:00:00Z"
    assert a["publication_date"] == "2026-08-23" and a["published_at"].startswith("2026-08-21T")
    assert a["buyer"] == "Bauamt Berlin" and a["value"] == "100" and a["currency"] == "EUR"
    assert a["url"].endswith(nid)
    assert json.loads(cursor)["completed_through"] == "2026-08-23"


def test_lot_groups_are_not_emitted_as_opportunities():
    nid = _uuid(1)
    lots = [
        _lot("LOT-0001", scheme="Lot"),
        _lot("GLO-0001", scheme="LotsGroup", deadline="2026-11-01"),
    ]
    rows, cursor = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(nid, _notice(nid, lots=lots)))}),
        initial_lookback_days=1,
        overlap_days=0,
    ).fetch_incremental(now=NOW)
    assert [r["external_id"] for r in rows] == ["folder-1::LOT-0001"]
    assert list(json.loads(cursor)["tracked"]) == ["folder-1::LOT-0001"]


def test_nonworks_ignored_even_with_construction_words():
    nid = _uuid(2)
    rows, cursor = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(nid, _notice(nid, kind="services", title="construction works")))}),
        initial_lookback_days=1,
        overlap_days=0,
    ).fetch_incremental(now=NOW)
    assert rows == [] and json.loads(cursor)["tracked"] == {}


def test_later_pubday_correction_wins_even_with_older_issue_date():
    first, second = _uuid(1), _uuid(3)
    session = FakeSession({
        "2026-08-22": _zip(_entry(first, _notice(first, issue="2026-08-20", lots=[_lot(deadline="2026-09-01")]))),
        "2026-08-23": _zip(_entry(second, _notice(second, issue="2026-08-19", lots=[_lot(deadline="2026-10-01")], title="Corrected"))),
    })
    rows, cursor = GermanDOEOpenDataConnector(
        session=session, initial_lookback_days=2, max_days_per_sync=3, overlap_days=0
    ).fetch_incremental(now=NOW)
    assert len(rows) == 1 and rows[0]["external_id"] == "folder-1::LOT-0001"
    assert rows[0]["deadline"] == "2026-10-01T09:00:00Z" and rows[0]["title"] == "Corrected"
    assert rows[0]["notice_identifier"] == second
    assert json.loads(cursor)["tracked"]["folder-1::LOT-0001"]["publication_day"] == "2026-08-23"


def test_terminal_winner_result_closes_visible_old_lot_but_untracked_is_silent():
    award = _uuid(4)
    connector = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(award, _award(award)))}), overlap_days=0
    )
    rows, cursor = connector.fetch_incremental(
        watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}), now=NOW
    )
    assert len(rows) == 1 and rows[0]["_lifecycle_only"]
    assert rows[0]["lifecycle_status"] == "awarded"
    assert rows[0]["doe_winner_selection_status"] == "selec-w"
    assert json.loads(cursor)["tracked"] == {} and json.loads(cursor)["closed"] == {}

    rows2, _ = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(award, _award(award)))}),
        initial_lookback_days=1,
        overlap_days=0,
    ).fetch_incremental(now=NOW)
    assert rows2 == []


def test_open_no_winner_remains_active_and_closed_no_winner_is_terminal():
    open_notice = _uuid(7)
    rows, cursor = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(open_notice, _award(open_notice, status="open-nw")))}),
        overlap_days=0,
    ).fetch_incremental(
        watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}),
        now=NOW,
    )
    assert len(rows) == 1
    assert rows[0]["is_actionable"] is True and rows[0]["lifecycle_status"] == "active"
    assert "folder-1::LOT-0001" in json.loads(cursor)["tracked"]

    next_now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    closed_notice = _uuid(8)
    rows2, cursor2 = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-24": _zip(_entry(closed_notice, _award(closed_notice, status="clos-nw")))}),
        overlap_days=0,
    ).fetch_incremental(watermark=cursor, now=next_now)
    assert len(rows2) == 1 and rows2[0]["_lifecycle_only"]
    assert rows2[0]["lifecycle_status"] == "closed_without_winner"
    assert rows2[0]["doe_winner_selection_status"] == "clos-nw"
    assert json.loads(cursor2)["tracked"] == {}


@pytest.mark.parametrize("status,include_status", [("future-code", True), ("", False)])
def test_unknown_or_missing_winner_status_fails_closed(status, include_status):
    award = _uuid(9)
    with pytest.raises(RuntimeError, match="winner-selection-status"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": _zip(_entry(award, _award(award, status=status, include_status=include_status)))}),
            overlap_days=0,
        ).fetch_incremental(
            watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}),
            now=NOW,
        )


def test_missing_deadline_pending_and_later_restored():
    first, later = _uuid(1), _uuid(5)
    rows1, cursor1 = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(first, _notice(first, lots=[_lot(deadline="")])))}),
        initial_lookback_days=1,
        overlap_days=0,
    ).fetch_incremental(now=NOW)
    assert rows1 == [] and "folder-1::LOT-0001" in json.loads(cursor1)["tracked"]
    next_now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    rows2, _ = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-24": _zip(_entry(later, _notice(later, lots=[_lot(deadline="2026-09-30")])))}),
        overlap_days=0,
    ).fetch_incremental(watermark=cursor1, now=next_now)
    assert len(rows2) == 1 and rows2[0]["is_actionable"]


def test_deadline_missing_or_elapsed_emits_tombstone_only_if_previously_visible():
    nid = _uuid(6)
    missing = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(nid, _notice(nid, lots=[_lot(deadline="")])))}),
        overlap_days=0,
    )
    rows, cursor = missing.fetch_incremental(
        watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}), now=NOW
    )
    assert len(rows) == 1 and rows[0]["lifecycle_status"] == "deadline_missing"
    assert json.loads(cursor)["tracked"]["folder-1::LOT-0001"]["was_visible"] is False

    expired = GermanDOEOpenDataConnector(session=FakeSession({"2026-08-23": _zip()}), overlap_days=0)
    rows2, cursor2 = expired.fetch_incremental(
        watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state("2026-08-23T00:00:00Z")}),
        now=NOW,
    )
    assert len(rows2) == 1 and rows2[0]["lifecycle_status"] == "deadline_elapsed"
    assert json.loads(cursor2)["tracked"] == {}


def test_long_catchup_suppresses_intermediate_truth_and_preserves_closure():
    nid, award = _uuid(1), _uuid(4)
    first = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-19": _zip(_entry(nid, _notice(nid, issue="2026-08-18")))}),
        initial_lookback_days=5,
        max_days_per_sync=2,
        overlap_days=0,
    )
    rows1, c1 = first.fetch_incremental(now=NOW)
    assert rows1 == [] and json.loads(c1)["completed_through"] == "2026-08-20"
    assert json.loads(c1)["tracked"]["folder-1::LOT-0001"]["was_visible"] is False

    visible_cursor = _cursor("2026-08-20", {"folder-1::LOT-0001": _state()})
    second = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-21": _zip(_entry(award, _award(award)))}),
        max_days_per_sync=1,
        overlap_days=0,
    )
    rows2, c2 = second.fetch_incremental(watermark=visible_cursor, now=NOW)
    assert rows2 == [] and "folder-1::LOT-0001" in json.loads(c2)["closed"]
    rows3, c3 = GermanDOEOpenDataConnector(
        session=FakeSession({}), max_days_per_sync=5, overlap_days=0
    ).fetch_incremental(watermark=c2, now=NOW)
    assert len(rows3) == 1 and rows3[0]["lifecycle_status"] == "awarded"
    assert json.loads(c3)["closed"] == {}


def test_cursor_validation_and_overlap_progress_guard():
    connector = GermanDOEOpenDataConnector(session=FakeSession({}))
    with pytest.raises(RuntimeError, match="cursor JSON"):
        connector.fetch_incremental(watermark="{bad", now=NOW)
    with pytest.raises(RuntimeError, match="cursor is ahead"):
        connector.fetch_incremental(watermark=_cursor("2026-08-24"), now=NOW)
    with pytest.raises(RuntimeError, match="cursor state"):
        connector.fetch_incremental(
            watermark=json.dumps({"completed_through": "2026-08-22", "tracked": [], "closed": {}}),
            now=NOW,
        )

    a = GermanDOEOpenDataConnector(
        session=FakeSession({}), initial_lookback_days=5, max_days_per_sync=2, overlap_days=10
    )
    _, c1 = a.fetch_incremental(now=NOW)
    b = GermanDOEOpenDataConnector(session=FakeSession({}), max_days_per_sync=2, overlap_days=10)
    _, c2 = b.fetch_incremental(watermark=c1, now=NOW)
    assert json.loads(c2)["completed_through"] > json.loads(c1)["completed_through"]


def test_zip_integrity_duplicate_nonzip_malformed_and_identity_mismatch():
    nid = _uuid(1)
    duplicate = _zip(_entry(nid, _notice(nid)), _entry(nid, _notice(nid)))
    with pytest.raises(RuntimeError, match="duplicate filenames"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": duplicate}), initial_lookback_days=1, overlap_days=0
        ).fetch_incremental(now=NOW)
    for body in (b"not zip", b"PKbroken"):
        with pytest.raises(RuntimeError):
            GermanDOEOpenDataConnector(
                session=FakeSession({"2026-08-23": body}), initial_lookback_days=1, overlap_days=0
            ).fetch_incremental(now=NOW)
    with pytest.raises(RuntimeError, match="malformed eForms XML"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": _zip((f"{nid}-01.xml", b"<broken"))}),
            initial_lookback_days=1,
            overlap_days=0,
        ).fetch_incremental(now=NOW)
    with pytest.raises(RuntimeError, match="filename/root"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": _zip((f"{nid}-01.xml", _notice(_uuid(2))))}),
            initial_lookback_days=1,
            overlap_days=0,
        ).fetch_incremental(now=NOW)


def test_archive_hard_limits_use_real_payload_sizes():
    single = _archive(1)
    with pytest.raises(RuntimeError, match="max_entry_bytes"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": single}),
            initial_lookback_days=1,
            overlap_days=0,
            max_entry_bytes=1024,
        ).fetch_incremental(now=NOW)

    many = _archive(8)
    assert len(many) > 1024
    with pytest.raises(RuntimeError, match="max_archive_bytes"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": many}),
            initial_lookback_days=1,
            overlap_days=0,
            max_archive_bytes=1024,
        ).fetch_incremental(now=NOW)
    with pytest.raises(RuntimeError, match="max_uncompressed_bytes"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": many}),
            initial_lookback_days=1,
            overlap_days=0,
            max_entry_bytes=10000,
            max_uncompressed_bytes=10000,
        ).fetch_incremental(now=NOW)
    with pytest.raises(RuntimeError, match="max_entries"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": many}),
            initial_lookback_days=1,
            overlap_days=0,
            max_entries=3,
        ).fetch_incremental(now=NOW)


def test_unknown_family_ignored_without_keywords_and_pii_not_persisted():
    nid = _uuid(1)
    unknown = b'<?xml version="1.0"?><PriorInformationNotice><Text>construction works</Text></PriorInformationNotice>'
    rows0, _ = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip((f"{nid}-01.xml", unknown))}),
        initial_lookback_days=1,
        overlap_days=0,
    ).fetch_incremental(now=NOW)
    assert rows0 == []

    rows, _ = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(nid, _notice(nid, contact=True)))}),
        initial_lookback_days=1,
        overlap_days=0,
    ).fetch_incremental(now=NOW)
    serialized = json.dumps(rows[0], ensure_ascii=False)
    assert "pii@example.invalid" not in serialized and "+49-secret" not in serialized
    assert "<ContractNotice" not in serialized
    assert rows[0]["reuse_license"] == "CC0-1.0" and rows[0]["source"] == SOURCE


def test_terminal_result_without_lot_identity_fails_closed():
    award = _uuid(4)
    with pytest.raises(RuntimeError, match="no lot identities"):
        GermanDOEOpenDataConnector(
            session=FakeSession({"2026-08-23": _zip(_entry(award, _award(award, lot_ids=())))}),
            overlap_days=0,
        ).fetch_incremental(
            watermark=_cursor("2026-08-22", {"folder-1::LOT-0001": _state()}),
            now=NOW,
        )
