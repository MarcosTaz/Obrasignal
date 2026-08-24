from datetime import datetime, timezone

from austria_kerndaten_incremental import AustriaKerndatenIncrementalConnector


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
KDQ = "https://publisher.example/kdq.xml"
DATASET = "dataset-equal-lastmod"


def notice(reference):
    return f"""<KD_8_1_Z2>
      <CONTRACTING_BODY><ADDRESS_CONTRACTING_BODY><OFFICIALNAME>Buyer</OFFICIALNAME><NATIONALID>AT1</NATIONALID></ADDRESS_CONTRACTING_BODY></CONTRACTING_BODY>
      <OBJECT_CONTRACT><TITLE><P>{reference}</P></TITLE><REFERENCE_NUMBER>{reference}</REFERENCE_NUMBER><CPV_MAIN><CPV_CODE CODE="45000000"/></CPV_MAIN><TYPE_CONTRACT CTYPE="WORKS"/><SHORT_DESCR><P>{reference}</P></SHORT_DESCR><NO_LOT_DIVISION/></OBJECT_CONTRACT>
      <PROCEDURE><PT_OPEN/><DATETIME_RECEIPT_TENDERS>2026-09-30T12:00:00+02:00</DATETIME_RECEIPT_TENDERS></PROCEDURE>
      <ADDITIONAL_CORE_DATA><DATE_FIRST_PUBLICATION>2026-08-24</DATE_FIRST_PUBLICATION><DATETIME_LAST_CHANGE>2026-08-24T10:00:00Z</DATETIME_LAST_CHANGE></ADDITIONAL_CORE_DATA>
    </KD_8_1_Z2>""".encode()


class Session:
    def __init__(self):
        self.headers = {}


class Connector(AustriaKerndatenIncrementalConnector):
    def __init__(self):
        super().__init__(session=Session(), max_notice_fetches_per_run=1, overlap_hours=0)
        stamp = "2026-08-24T10:00:00Z"
        self.items = [
            {"id": "a", "lastmod": stamp, "url": "https://publisher.example/a.xml"},
            {"id": "b", "lastmod": stamp, "url": "https://publisher.example/b.xml"},
        ]
        self.payloads = {
            "https://publisher.example/a.xml": notice("A"),
            "https://publisher.example/b.xml": notice("B"),
        }
        self.calls = []

    def _discover(self, cursor):
        return {DATASET: {"urls": [KDQ]}}

    def _kdq_items(self, url):
        return list(self.items)

    def _notice_payload(self, url):
        self.calls.append(url)
        return self.payloads[url]


def test_equal_lastmod_items_resume_by_item_id_without_skip_or_duplicate():
    connector = Connector()
    rows1, cursor1 = connector.fetch_incremental(now=NOW)
    assert rows1 == []
    assert connector.calls == ["https://publisher.example/a.xml"]

    rows2, _cursor2 = connector.fetch_incremental(watermark=cursor1, now=NOW)
    assert {row["procedure_reference"] for row in rows2} == {"A", "B"}
    assert connector.calls == [
        "https://publisher.example/a.xml",
        "https://publisher.example/b.xml",
    ]
