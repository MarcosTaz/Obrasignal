from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import pytest

from germany_doe import GermanDOECursor, GermanDOEOpenDataConnector


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


def test_later_open_nw_reopens_after_terminal_was_committed_in_prior_sync():
    original = _uuid(1)
    terminal = _uuid(2)
    reopened = _uuid(3)

    first = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-22": _zip(_entry(original, _notice(original)))}),
        initial_lookback_days=1,
        overlap_days=0,
    )
    rows1, cursor1 = first.fetch_incremental(
        now=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    )
    assert len(rows1) == 1 and rows1[0]["is_actionable"] is True

    second = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-23": _zip(_entry(terminal, _result(terminal, "selec-w", "2026-08-23")))}),
        overlap_days=0,
    )
    rows2, cursor2 = second.fetch_incremental(
        watermark=cursor1,
        now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
    )
    assert len(rows2) == 1 and rows2[0]["_lifecycle_only"]
    assert rows2[0]["lifecycle_status"] == "awarded"
    state2 = json.loads(cursor2)
    assert state2["closed"] == {}
    assert "folder-1::LOT-0001" in state2["recently_closed"]
    assert state2["recently_closed"]["folder-1::LOT-0001"]["closure_emitted"] is True

    third = GermanDOEOpenDataConnector(
        session=FakeSession({"2026-08-24": _zip(_entry(reopened, _result(reopened, "open-nw", "2026-08-24")))}),
        overlap_days=0,
    )
    rows3, cursor3 = third.fetch_incremental(
        watermark=cursor2,
        now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
    )

    assert len(rows3) == 1
    row = rows3[0]
    assert row["external_id"] == "folder-1::LOT-0001"
    assert row["is_actionable"] is True
    assert row["lifecycle_status"] == "active"
    assert row["doe_winner_selection_status"] == "open-nw"
    assert row["deadline"] == "2026-10-20T09:00:00Z"
    assert row["notice_identifier"] == reopened
    state3 = json.loads(cursor3)
    assert "folder-1::LOT-0001" in state3["tracked"]
    assert state3["closed"] == {}
    assert state3["recently_closed"] == {}


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
    assert state["recently_closed"] == {}


def test_recently_closed_memory_is_pruned_by_bounded_retention():
    old = {
        "external_id": "folder-old::LOT-0001",
        "procedure_id": "folder-old",
        "publication_day": "2026-06-01",
        "source_updated_at": "2026-06-01T09:00:00Z",
        "closed": True,
        "was_visible": True,
        "closure_emitted": True,
    }
    watermark = GermanDOECursor(
        "2026-08-23", {}, {}, {"folder-old::LOT-0001": old}
    ).encode()
    connector = GermanDOEOpenDataConnector(
        session=FakeSession({}),
        overlap_days=0,
        closed_retention_days=30,
    )
    rows, cursor = connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
    )
    assert rows == []
    assert json.loads(cursor)["recently_closed"] == {}


def test_recently_closed_memory_has_hard_cap():
    recent = {
        "a": {"external_id": "a", "publication_day": "2026-08-23"},
        "b": {"external_id": "b", "publication_day": "2026-08-23"},
    }
    watermark = GermanDOECursor("2026-08-23", {}, {}, recent).encode()
    connector = GermanDOEOpenDataConnector(
        session=FakeSession({}),
        max_recently_closed=1,
        overlap_days=0,
    )
    with pytest.raises(RuntimeError, match="max_recently_closed"):
        connector.fetch_incremental(
            watermark=watermark,
            now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
        )
