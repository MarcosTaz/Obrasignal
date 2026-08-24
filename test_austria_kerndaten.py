from datetime import datetime, timezone
import json

import pytest

from austria_kerndaten import (
    AustriaKerndatenConnector,
    AustriaKerndatenCursor,
    _parse_notice,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
DATASET = "dataset-at-1"
KDQ = "https://publisher.example/kdq.xml"


def legacy_xml(*, root="KD_8_1_Z2", item_title="Sanierung Dach- und Fassadenflächen BSZ Traun", description="Sanierung der Dach- und Fassadenflächen beim Bundesschulzentrum Traun", reference="", buyer_id="", buyer="Bildungsdirektion OÖ", ctype="WORKS", cpv="45000000", deadline="2026-08-25T09:00:00+02:00", first="2026-07-28", changed="2026-07-28T09:00:00+02:00", document="https://publisher.example/human/1", procedure="PT_OPEN"):
    return f"""<{root}>
      <CONTRACTING_BODY>
        <ADDRESS_CONTRACTING_BODY><OFFICIALNAME>{buyer}</OFFICIALNAME><NATIONALID>{buyer_id}</NATIONALID><PHONE>+43 123</PHONE><E_MAIL>pii@example.at</E_MAIL></ADDRESS_CONTRACTING_BODY>
        <URL_DOCUMENT>{document}</URL_DOCUMENT>
      </CONTRACTING_BODY>
      <OBJECT_CONTRACT>
        <TITLE><P>{item_title}</P></TITLE><REFERENCE_NUMBER>{reference}</REFERENCE_NUMBER>
        <CPV_MAIN><CPV_CODE CODE="{cpv}"/></CPV_MAIN><TYPE_CONTRACT CTYPE="{ctype}"/>
        <SHORT_DESCR><P>{description}</P></SHORT_DESCR><NO_LOT_DIVISION/>
        <OBJECT_DESCR><NUTS CODE="AT31"/><DATE_START>2026-09-01</DATE_START><DATE_END>2028-12-31</DATE_END></OBJECT_DESCR>
      </OBJECT_CONTRACT>
      <PROCEDURE><{procedure}/><DATETIME_RECEIPT_TENDERS>{deadline}</DATETIME_RECEIPT_TENDERS></PROCEDURE>
      <ADDITIONAL_CORE_DATA><DATE_FIRST_PUBLICATION>{first}</DATE_FIRST_PUBLICATION><DATETIME_LAST_CHANGE>{changed}</DATETIME_LAST_CHANGE></ADDITIONAL_CORE_DATA>
    </{root}>""".encode()


def eforms_xml(*, project_type="works", folder="folder-1", notice_id="notice-1", lot_id="LOT-1", deadline_date="2026-09-03+02:00", deadline_time="10:00:00+02:00"):
    return f"""<ContractNotice>
      <UBLExtensions><UBLExtension><ExtensionContent><EformsExtension><Organizations>
        <Organization><Company><PartyIdentification><ID>ORG-1</ID></PartyIdentification><PartyName><Name>Stadt Wien</Name></PartyName><PartyLegalEntity><CompanyID>ATU123</CompanyID></PartyLegalEntity></Company></Organization>
      </Organizations></EformsExtension></ExtensionContent></UBLExtension></UBLExtensions>
      <ID>{notice_id}</ID><ContractFolderID>{folder}</ContractFolderID><IssueDate>2026-08-24+02:00</IssueDate><IssueTime>10:30:00+02:00</IssueTime>
      <ContractingParty><Party><PartyIdentification><ID>ORG-1</ID></PartyIdentification></Party></ContractingParty>
      <TenderingProcess><ProcedureCode>open</ProcedureCode></TenderingProcess>
      <ProcurementProject><Name>Brückensanierung</Name><Description>Bauarbeiten</Description><ProcurementTypeCode>{project_type}</ProcurementTypeCode><MainCommodityClassification><ItemClassificationCode listName="cpv">45221110</ItemClassificationCode></MainCommodityClassification></ProcurementProject>
      <ProcurementProjectLot><ID>{lot_id}</ID><Name>Los 1</Name><MainCommodityClassification><ItemClassificationCode listName="cpv">45221110</ItemClassificationCode></MainCommodityClassification><TenderingProcess><TenderSubmissionDeadlinePeriod><EndDate>{deadline_date}</EndDate><EndTime>{deadline_time}</EndTime></TenderSubmissionDeadlinePeriod></TenderingProcess></ProcurementProjectLot>
      <AdditionalDocumentReference><Attachment><ExternalReference><URI>https://auftrag.at/project/1</URI></ExternalReference></Attachment></AdditionalDocumentReference>
    </ContractNotice>""".encode()


def kdq_xml(items):
    body = "".join(
        f'<item id="{item_id}" lastmod="{lastmod}"><url>{url}</url></item>'
        for item_id, lastmod, url in items
    )
    return f"<kdq><header/><items>{body}</items></kdq>".encode()


class Response:
    def __init__(self, *, payload=b"", json_payload=None, status=200, content_length=None):
        self.payload = payload
        self.json_payload = json_payload
        self.status_code = status
        self.headers = {"content-length": str(len(payload) if content_length is None else content_length)}
        self.url = "https://example.invalid/resource"
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):
        if self.json_payload is None:
            return json.loads(self.payload.decode())
        return self.json_payload
    def iter_content(self, chunk_size=131072):
        for i in range(0, len(self.payload), chunk_size):
            yield self.payload[i:i + chunk_size]
    def close(self):
        return None


class Session:
    def __init__(self, *, notices, kdqs=None, datasets=None, search_ids=None, fail_urls=None, content_lengths=None):
        self.headers = {}
        self.notices = notices
        self.kdqs = kdqs or {KDQ: kdq_xml([(key, "2026-08-24T10:00:00+02:00", key) for key in notices])}
        self.datasets = datasets or {DATASET: [KDQ]}
        self.search_ids = search_ids or list(self.datasets)
        self.fail_urls = set(fail_urls or [])
        self.content_lengths = content_lengths or {}
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs.get("params")))
        if url in self.fail_urls:
            return Response(status=503)
        if url.endswith("/api/hub/search/search"):
            rows = [{"id": dataset_id} for dataset_id in self.search_ids]
            return Response(json_payload={"result": {"count": len(rows), "results": rows}})
        marker = "/api/hub/repo/datasets/"
        if marker in url:
            dataset_id = url.split(marker, 1)[1]
            graph = [{"dcat:accessURL": {"@id": item}} for item in self.datasets.get(dataset_id, [])]
            return Response(json_payload={"@graph": graph})
        if url in self.kdqs:
            payload = self.kdqs[url]
            return Response(payload=payload, content_length=self.content_lengths.get(url))
        if url in self.notices:
            payload = self.notices[url]
            return Response(payload=payload, content_length=self.content_lengths.get(url))
        raise AssertionError(f"unexpected URL {url}")


def parse(payload, *, item_id="pub-1", lastmod="2026-08-24T10:00:00+02:00"):
    return _parse_notice(payload, dataset_id=DATASET, item_id=item_id, item_lastmod=lastmod, notice_url=f"https://publisher.example/{item_id}.xml")


def test_legacy_z2_uses_native_works_cpv_deadline_and_excludes_contact_pii():
    state = parse(legacy_xml())[0]
    assert state["contract_type"] == "works"
    assert state["cpv_codes"] == ["45000000"]
    assert state["deadline"] == "2026-08-25T07:00:00Z"
    assert state["title"] == "Sanierung Dach- und Fassadenflächen BSZ Traun"
    assert state["url"] == "https://publisher.example/human/1"
    dump = json.dumps(state)
    assert "pii@example.at" not in dump and "+43 123" not in dump
    assert parse(legacy_xml(ctype="SERVICES")) == []


def test_z1_prior_information_is_fail_closed_even_with_deadline():
    assert parse(legacy_xml(root="KD_8_1_Z1", deadline="2026-09-20T12:00:00+02:00")) == []


def test_reference_identity_is_stable_across_deadline_correction():
    first = parse(legacy_xml(reference="E-2026-7", buyer_id="FN 227986z", deadline="2026-08-29T12:00:00+02:00"))[0]
    second = parse(legacy_xml(reference="E-2026-7", buyer_id="FN 227986z", deadline="2026-09-10T12:00:00+02:00", changed="2026-08-25T09:00:00+02:00"), item_id="pub-2", lastmod="2026-08-25T09:00:00+02:00")[0]
    assert first["external_id"] == second["external_id"]
    assert first["deadline"] != second["deadline"]


def test_anonymous_publisher_duplicates_fold_to_one_opportunity_and_keep_aliases():
    urls = [f"https://publisher.example/{i}.xml" for i in range(4)]
    session = Session(
        notices={url: legacy_xml(document=f"https://publisher.example/human/{i}") for i, url in enumerate(urls)},
        kdqs={KDQ: kdq_xml([(str(i), "2026-08-24T10:00:00+02:00", url) for i, url in enumerate(urls)])},
    )
    connector = AustriaKerndatenConnector(session=session, initial_lookback_days=10)
    rows, cursor = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["is_actionable"] is True
    assert len(rows[0]["publication_aliases"]) == 4
    tracked = AustriaKerndatenCursor.decode(cursor).tracked
    assert len(tracked) == 1
    assert len(next(iter(tracked.values()))["publication_aliases"]) == 4


def test_eforms_contract_notice_is_lot_level_and_works_only():
    state = parse(eforms_xml(), item_id="ef-1")[0]
    assert state["external_id"] == f"{DATASET}:eforms:folder-1:LOT-1"
    assert state["buyer"] == "Stadt Wien"
    assert state["cpv_codes"] == ["45221110"]
    assert state["deadline"] == "2026-09-03T08:00:00Z"
    assert state["payload_family"] == "eforms_ubl_2_3"
    assert parse(eforms_xml(project_type="services"), item_id="ef-2") == []


def test_unknown_non_kerndaten_root_fails_closed():
    with pytest.raises(RuntimeError, match="unsupported notice root"):
        parse(b"<mystery/>")


def test_deadline_elapsed_emits_lifecycle_tombstone_without_legacy_row_shape_change():
    url = "https://publisher.example/open.xml"
    early = datetime(2026, 8, 24, 6, 0, tzinfo=timezone.utc)
    payload = legacy_xml(deadline="2026-08-24T10:00:00+02:00")
    connector = AustriaKerndatenConnector(session=Session(notices={url: payload}, kdqs={KDQ: kdq_xml([("one", "2026-08-24T07:00:00+02:00", url)])}))
    rows, watermark = connector.fetch_incremental(now=early)
    assert len(rows) == 1 and rows[0]["is_actionable"] is True

    # No changed notice is required for the deadline tombstone: tracked state is enough.
    later_session = Session(notices={url: payload}, kdqs={KDQ: kdq_xml([("one", "2026-08-24T07:00:00+02:00", url)])})
    rows, cursor = AustriaKerndatenConnector(session=later_session, overlap_hours=0).fetch_incremental(watermark=watermark, now=NOW)
    assert len(rows) == 1
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "deadline_elapsed"
    assert AustriaKerndatenCursor.decode(cursor).tracked == {}


def test_correction_updates_existing_visible_opportunity_instead_of_duplicating():
    url = "https://publisher.example/correction.xml"
    seed_session = Session(notices={url: legacy_xml(reference="R-1", buyer_id="FN1", deadline="2026-08-28T12:00:00+02:00")}, kdqs={KDQ: kdq_xml([("pub", "2026-08-24T08:00:00+02:00", url)])})
    rows, watermark = AustriaKerndatenConnector(session=seed_session).fetch_incremental(now=NOW)
    original_id = rows[0]["external_id"]

    changed = legacy_xml(reference="R-1", buyer_id="FN1", deadline="2026-09-04T12:00:00+02:00", changed="2026-08-25T08:00:00+02:00")
    correction_session = Session(notices={url: changed}, kdqs={KDQ: kdq_xml([("pub", "2026-08-25T08:00:00+02:00", url)])})
    rows, _ = AustriaKerndatenConnector(session=correction_session).fetch_incremental(watermark=watermark, now=datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["external_id"] == original_id
    assert rows[0]["deadline"] == "2026-09-04T10:00:00Z"


def test_kdq_failure_does_not_advance_that_kdq_when_another_publisher_succeeds():
    kdq_ok = "https://ok.example/kdq.xml"
    kdq_bad = "https://bad.example/kdq.xml"
    notice = "https://ok.example/n.xml"
    session = Session(
        notices={notice: legacy_xml()},
        datasets={"one": [kdq_ok], "two": [kdq_bad]},
        kdqs={kdq_ok: kdq_xml([("n", "2026-08-24T10:00:00+02:00", notice)]), kdq_bad: b"<broken"},
    )
    rows, cursor = AustriaKerndatenConnector(session=session).fetch_incremental(now=NOW)
    decoded = AustriaKerndatenCursor.decode(cursor)
    assert len(rows) == 1
    assert kdq_ok in decoded.kdq_observed
    assert kdq_bad not in decoded.kdq_observed


def test_all_kdqs_failed_is_hard_failure_and_cursor_not_returned():
    bad = "https://bad.example/kdq.xml"
    session = Session(notices={}, datasets={DATASET: [bad]}, kdqs={bad: b"<broken"})
    with pytest.raises(RuntimeError, match="no KDQ completed successfully; cursor not advanced"):
        AustriaKerndatenConnector(session=session).fetch_incremental(now=NOW)


def test_catalogue_and_resource_hard_limits_fail_closed():
    many = [f"d{i}" for i in range(3)]
    session = Session(notices={}, datasets={item: [f"https://{item}.example/kdq"] for item in many}, search_ids=many)
    with pytest.raises(RuntimeError, match="max_datasets=2"):
        AustriaKerndatenConnector(session=session, max_datasets=2).fetch_incremental(now=NOW)

    url = "https://publisher.example/n.xml"
    big = Session(
        notices={url: legacy_xml()},
        kdqs={KDQ: kdq_xml([("n", "2026-08-24T10:00:00+02:00", url)])},
        content_lengths={KDQ: 999999},
    )
    with pytest.raises(RuntimeError, match="no KDQ completed successfully"):
        AustriaKerndatenConnector(session=big, max_kdq_bytes=1000).fetch_incremental(now=NOW)


def test_invalid_and_future_cursor_are_rejected():
    with pytest.raises(RuntimeError, match="invalid AT_KERNDATEN cursor"):
        AustriaKerndatenCursor.decode("not-json")
    future = AustriaKerndatenCursor(observed_through="2026-08-25T12:00:00Z", datasets={}, kdq_observed={}, tracked={}).encode()
    with pytest.raises(RuntimeError, match="cursor is in the future"):
        AustriaKerndatenConnector(session=Session(notices={})).fetch_incremental(watermark=future, now=NOW)
