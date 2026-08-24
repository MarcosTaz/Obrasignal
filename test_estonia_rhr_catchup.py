from datetime import datetime, timezone
import re

from estonia_rhr import EERHRCursor, EstoniaRHRConnector


NOW = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
EMPTY = b"<OPEN-DATA></OPEN-DATA>"


def notice(folder, notice_id, issue_date, *, deadline="2026-12-01+02:00", lot="LOT-0000"):
    return f"""<ContractNotice><ID>{notice_id}</ID><ContractFolderID>{folder}</ContractFolderID>
    <IssueDate>{issue_date}</IssueDate><IssueTime>09:00:00.000+02:00</IssueTime><NoticeTypeCode>cn-standard</NoticeTypeCode>
    <ProcurementProject><ID>P-1</ID><Name>Ehitus</Name><ProcurementTypeCode>works</ProcurementTypeCode><MainCommodityClassification><ItemClassificationCode listName="cpv">45210000</ItemClassificationCode></MainCommodityClassification></ProcurementProject>
    <ProcurementProjectLot><ID>{lot}</ID><MainCommodityClassification><ItemClassificationCode listName="cpv">45210000</ItemClassificationCode></MainCommodityClassification><TenderingProcess><TenderSubmissionDeadlinePeriod><EndDate>{deadline}</EndDate><EndTime>12:00:00.000+02:00</EndTime></TenderSubmissionDeadlinePeriod></TenderingProcess></ProcurementProjectLot>
    </ContractNotice>"""


def award(folder, notice_id, issue_date, *, lot="LOT-0000"):
    return f"""<ContractAwardNotice><ID>{notice_id}</ID><ContractFolderID>{folder}</ContractFolderID>
    <IssueDate>{issue_date}</IssueDate><IssueTime>09:00:00.000+02:00</IssueTime><NoticeTypeCode>can-standard</NoticeTypeCode>
    <NoticeResult><LotResult><TenderLot><ID>{lot}</ID></TenderLot></LotResult></NoticeResult>
    <ProcurementProject><ID>P-1</ID><Name>Ehitus</Name><ProcurementTypeCode>works</ProcurementTypeCode></ProcurementProject>
    </ContractAwardNotice>"""


def package(*rows):
    return ("<OPEN-DATA>" + "".join(rows) + "</OPEN-DATA>").encode()


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.headers = {"content-length": str(len(payload))}
    def raise_for_status(self):
        return None
    def iter_content(self, chunk_size=131072):
        yield self.payload
    def close(self):
        return None


class MonthSession:
    def __init__(self, notices=None, awards=None):
        self.notices = notices or {}
        self.awards = awards or {}
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(url)
        match = re.search(r"/(notice(?:_award)?)/(\d{4})/month/(\d+)/xml$", url)
        assert match
        surface, year, month = match.group(1), int(match.group(2)), int(match.group(3))
        mapping = self.awards if surface == "notice_award" else self.notices
        return Response(mapping.get((year, month), EMPTY))


def visible_state():
    return {
        "external_id": "folder-old::LOT-0000",
        "procedure_id": "folder-old",
        "lot_id": "LOT-0000",
        "lot_count": 1,
        "notice_id": "old-notice",
        "notice_type": "cn-standard",
        "event_kind": "notice",
        "closed": False,
        "title": "Old visible works tender",
        "description": "Old visible works tender",
        "buyer": "",
        "place": "",
        "cpv_codes": ["45210000"],
        "deadline": "2026-12-01T10:00:00Z",
        "value": "",
        "currency": "",
        "first_published_at": "2026-01-10T07:00:00Z",
        "source_updated_at": "2026-01-10T07:00:00Z",
        "url": "",
        "procurement_method": "",
        "was_visible": True,
    }


def test_long_outage_is_chunked_and_emits_only_final_truth():
    seed = EERHRCursor(
        "2026-01-15T12:00:00Z",
        {"folder-old::LOT-0000": visible_state()},
        ("2026-01",),
    ).encode()
    first_session = MonthSession(
        notices={(2026, 2): package(notice("folder-new", "new-notice", "2026-02-10+02:00"))},
    )
    first = EstoniaRHRConnector(
        session=first_session,
        initial_months=1,
        overlap_months=0,
        max_months_per_sync=2,
    )
    rows, partial = first.fetch_incremental(watermark=seed, now=NOW)
    decoded = EERHRCursor.decode(partial)

    assert rows == []
    assert decoded.observed_through == "2026-01-15T12:00:00Z"
    assert decoded.catchup_next == "2026-03"
    assert set(decoded.tracked) == {"folder-old::LOT-0000", "folder-new::LOT-0000"}
    assert all("/2026/month/1/xml" in url or "/2026/month/2/xml" in url for url in first_session.calls)

    second_session = MonthSession(
        awards={
            (2026, 3): package(
                award("folder-old", "old-award", "2026-03-05+02:00"),
                award("folder-new", "new-award", "2026-03-06+02:00"),
            )
        }
    )
    second = EstoniaRHRConnector(
        session=second_session,
        initial_months=1,
        overlap_months=0,
        max_months_per_sync=2,
    )
    rows, final_cursor = second.fetch_incremental(watermark=partial, now=NOW)
    final = EERHRCursor.decode(final_cursor)

    assert len(rows) == 1
    assert rows[0]["external_id"] == "folder-old::LOT-0000"
    assert rows[0]["is_actionable"] is False
    assert rows[0]["lifecycle_status"] == "result_published"
    assert final.catchup_next == ""
    assert final.observed_through == "2026-04-15T12:00:00Z"
    assert final.tracked == {}
    assert all("/2026/month/3/xml" in url or "/2026/month/4/xml" in url for url in second_session.calls)


def test_new_active_tender_found_during_catchup_waits_until_caught_up():
    seed = EERHRCursor("2026-01-15T12:00:00Z", {}, ("2026-01",)).encode()
    first = EstoniaRHRConnector(
        session=MonthSession(notices={(2026, 2): package(notice("folder-new", "new-notice", "2026-02-10+02:00"))}),
        initial_months=1,
        overlap_months=0,
        max_months_per_sync=2,
    )
    rows, partial = first.fetch_incremental(watermark=seed, now=NOW)
    assert rows == []

    second = EstoniaRHRConnector(
        session=MonthSession(),
        initial_months=1,
        overlap_months=0,
        max_months_per_sync=2,
    )
    rows, cursor = second.fetch_incremental(watermark=partial, now=NOW)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "folder-new::LOT-0000"
    assert rows[0]["is_actionable"] is True
    assert "folder-new::LOT-0000" in EERHRCursor.decode(cursor).tracked
