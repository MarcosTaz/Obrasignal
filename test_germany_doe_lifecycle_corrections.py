from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

from germany_doe import GermanDOEOpenDataConnector


class FakeResponse:
    def __init__(self, body=b""):
        self.body = body

    def raise_for_status(self):
        return None

    def iter_content(self, size):
        for index in range(0, len(self.body), max(1, size)):
            yield self.body[index:index + size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, by_day):
        self.by_day = dict(by_day)

    def get(self, url, *, params, headers, timeout, stream, allow_redirects):
        return FakeResponse(self.by_day.get(params["pubDay"], _zip()))


def _zip(*entries):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in entries:
            zf.writestr(name, body)
    return buf.getvalue()


def _uuid(index):
    return f"00000000-0000-0000-0000-{int(index):012d}"


def _entry(notice_id, body, version=1):
    return f"{notice_id}-{version:02d}.xml", body


def _notice(notice_id):
    return f"""<?xml version="1.0"?>
<ContractNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac">
  <cbc:ID>{notice_id}</cbc:ID>
  <cbc:ContractFolderID>folder-1</cbc:ContractFolderID>
  <cbc:IssueDate>2026-08-22+02:00</cbc:IssueDate>
  <cbc:IssueTime>06:30:00+02:00</cbc:IssueTime>
  <cbc:NoticeTypeCode>competition</cbc:NoticeTypeCode>
  <cac:ProcurementProject>
    <cbc:Name>Gleisbau</cbc:Name>
    <cbc:Description>Öffentliche Bauleistung</cbc:Description>
    <cbc:ProcurementTypeCode>works</cbc:ProcurementTypeCode>
    <cac:MainCommodityClassification>
      <cbc:ItemClassificationCode listName="cpv">45234116</cbc:ItemClassificationCode>
    </cac:MainCommodityClassification>
  </cac:ProcurementProject>
  <cac:ProcurementProjectLot>
    <cbc:ID schemeName="Lot">LOT-0001</cbc:ID>
    <cbc:Name>Los 1</cbc:Name>
    <cac:ProcurementProject>
      <cac:MainCommodityClassification>
        <cbc:ItemClassificationCode listName="cpv">45234116</cbc:ItemClassificationCode>
      </cac:MainCommodityClassification>
    </cac:ProcurementProject>
    <cac:TenderingProcess>
      <cac:TenderSubmissionDeadlinePeriod>
        <cbc:EndDate>2026-10-20+02:00</cbc:EndDate>
        <cbc:EndTime>11:00:00+02:00</cbc:EndTime>
      </cac:TenderSubmissionDeadlinePeriod>
    </cac:TenderingProcess>
  </cac:ProcurementProjectLot>
</ContractNotice>""".encode()


def _result(notice_id, status, issue_day):
    return f"""<?xml version="1.0"?>
<ContractAwardNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac" xmlns:efac="urn:efac">
  <cbc:ID>{notice_id}</cbc:ID>
  <cbc:ContractFolderID>folder-1</cbc:ContractFolderID>
  <cbc:IssueDate>{issue_day}+02:00</cbc:IssueDate>
  <cbc:IssueTime>09:00:00+02:00</cbc:IssueTime>
  <cbc:NoticeTypeCode>result</cbc:NoticeTypeCode>
  <cac:ProcurementProject><cbc:ProcurementTypeCode>works</cbc:ProcurementTypeCode></cac:ProcurementProject>
  <efac:NoticeResult>
    <efac:LotResult>
      <cbc:TenderResultCode listName="winner-selection-status">{status}</cbc:TenderResultCode>
      <cac:TenderLot><cbc:ID schemeName="Lot">LOT-0001</cbc:ID></cac:TenderLot>
    </efac:LotResult>
  </efac:NoticeResult>
</ContractAwardNotice>""".encode()


def test_later_open_nw_reopens_known_lot_after_terminal_result():
    original = _uuid(1)
    terminal = _uuid(2)
    reopened = _uuid(3)
    connector = GermanDOEOpenDataConnector(
        session=FakeSession({
            "2026-08-22": _zip(_entry(original, _notice(original))),
            "2026-08-23": _zip(_entry(terminal, _result(terminal, "selec-w", "2026-08-23"))),
            "2026-08-24": _zip(_entry(reopened, _result(reopened, "open-nw", "2026-08-24"))),
        }),
        initial_lookback_days=3,
        max_days_per_sync=4,
        overlap_days=0,
    )

    rows, cursor = connector.fetch_incremental(
        now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["external_id"] == "folder-1::LOT-0001"
    assert row["is_actionable"] is True
    assert row["lifecycle_status"] == "active"
    assert row["doe_winner_selection_status"] == "open-nw"
    assert row["deadline"] == "2026-10-20T09:00:00Z"
    assert row["notice_identifier"] == reopened
    state = json.loads(cursor)
    assert "folder-1::LOT-0001" in state["tracked"]
    assert state["closed"] == {}


def test_open_nw_result_does_not_invent_untracked_opportunity():
    reopened = _uuid(4)
    connector = GermanDOEOpenDataConnector(
        session=FakeSession({
            "2026-08-24": _zip(_entry(reopened, _result(reopened, "open-nw", "2026-08-24"))),
        }),
        initial_lookback_days=1,
        overlap_days=0,
    )

    rows, cursor = connector.fetch_incremental(
        now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    )

    assert rows == []
    state = json.loads(cursor)
    assert state["tracked"] == {}
    assert state["closed"] == {}
