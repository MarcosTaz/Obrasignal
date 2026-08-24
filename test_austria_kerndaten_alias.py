from datetime import datetime, timezone
import json

from austria_kerndaten import AustriaKerndatenConnector, AustriaKerndatenCursor


DATASET = "dataset-at-alias"
KDQ = "https://publisher.example/kdq.xml"
NOTICE = "https://publisher.example/notice.xml"


def legacy_xml(*, title, description, changed, deadline):
    return f"""<KD_8_1_Z2>
      <CONTRACTING_BODY>
        <ADDRESS_CONTRACTING_BODY><OFFICIALNAME>Anonymous authority</OFFICIALNAME><NATIONALID/></ADDRESS_CONTRACTING_BODY>
        <URL_DOCUMENT>https://publisher.example/human</URL_DOCUMENT>
      </CONTRACTING_BODY>
      <OBJECT_CONTRACT>
        <TITLE><P>{title}</P></TITLE><REFERENCE_NUMBER/>
        <CPV_MAIN><CPV_CODE CODE="45210000"/></CPV_MAIN><TYPE_CONTRACT CTYPE="WORKS"/>
        <SHORT_DESCR><P>{description}</P></SHORT_DESCR><NO_LOT_DIVISION/>
        <OBJECT_DESCR><NUTS CODE="AT13"/></OBJECT_DESCR>
      </OBJECT_CONTRACT>
      <PROCEDURE><PT_OPEN/><DATETIME_RECEIPT_TENDERS>{deadline}</DATETIME_RECEIPT_TENDERS></PROCEDURE>
      <ADDITIONAL_CORE_DATA><DATE_FIRST_PUBLICATION>2026-08-20</DATE_FIRST_PUBLICATION><DATETIME_LAST_CHANGE>{changed}</DATETIME_LAST_CHANGE></ADDITIONAL_CORE_DATA>
    </KD_8_1_Z2>""".encode()


def kdq_xml(lastmod):
    return f'<kdq><items><item id="pub" lastmod="{lastmod}"><url>{NOTICE}</url></item></items></kdq>'.encode()


class Response:
    def __init__(self, *, payload=b"", json_payload=None):
        self.payload = payload
        self.json_payload = json_payload
        self.status_code = 200
        self.headers = {"content-length": str(len(payload))}

    def raise_for_status(self):
        return None

    def json(self):
        return self.json_payload if self.json_payload is not None else json.loads(self.payload.decode())

    def iter_content(self, chunk_size=131072):
        for offset in range(0, len(self.payload), chunk_size):
            yield self.payload[offset:offset + chunk_size]

    def close(self):
        return None


class Session:
    def __init__(self, *, notice, lastmod):
        self.headers = {}
        self.notice = notice
        self.lastmod = lastmod

    def get(self, url, **kwargs):
        if url.endswith("/api/hub/search/search"):
            return Response(json_payload={"result": {"count": 1, "results": [{"id": DATASET}]}})
        if "/api/hub/repo/datasets/" in url:
            return Response(json_payload={"@graph": [{"dcat:accessURL": {"@id": KDQ}}]})
        if url == KDQ:
            return Response(payload=kdq_xml(self.lastmod))
        if url == NOTICE:
            return Response(payload=self.notice)
        raise AssertionError(f"unexpected URL {url}")


def test_same_legacy_alias_keeps_canonical_id_when_mutable_semantics_change():
    first_now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    first = legacy_xml(
        title="Schulsanierung Alt",
        description="Fassade und Dach Alt",
        changed="2026-08-24T10:00:00+02:00",
        deadline="2026-09-10T12:00:00+02:00",
    )
    rows, watermark = AustriaKerndatenConnector(
        session=Session(notice=first, lastmod="2026-08-24T10:00:00+02:00")
    ).fetch_incremental(now=first_now)
    assert len(rows) == 1
    original_id = rows[0]["external_id"]

    corrected = legacy_xml(
        title="Schulsanierung Neu",
        description="Fassade, Dach und Fenster korrigiert",
        changed="2026-08-25T09:00:00+02:00",
        deadline="2026-09-18T12:00:00+02:00",
    )
    rows, cursor = AustriaKerndatenConnector(
        session=Session(notice=corrected, lastmod="2026-08-25T09:00:00+02:00")
    ).fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    assert rows[0]["external_id"] == original_id
    assert rows[0]["title"] == "Schulsanierung Neu"
    assert rows[0]["deadline"] == "2026-09-18T10:00:00Z"
    tracked = AustriaKerndatenCursor.decode(cursor).tracked
    assert list(tracked) == [original_id]
    assert tracked[original_id]["publication_aliases"] == [f"{DATASET}:pub"]
