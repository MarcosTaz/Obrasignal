import sqlite3

import pytest
import requests

from kuwait_capt import (
    CAPTTender,
    KuwaitCAPTConnector,
    KuwaitCAPTSourceError,
    fetch_normalized_construction_tenders,
    fetch_open_tenders,
    is_construction_relevant,
    normalize_construction_tenders,
    normalize_tender,
    parse_open_tenders,
)
from signal_store import get_signal_record, persist_signal_records


PAGE1 = """
<html><body><h1>المناقصات المطروحة</h1>
<div>الرقم</div><div>6/2025/2026</div><div>الجهة</div><div>الإدارة العامة للطيران المدني</div>
<div>الموضوع</div><div>اعمال صيانة و ترميم المباني و الاعمال الانشائية في مواقع مختلفة للطيران المدني</div>
<div>تاريخ الطلب</div><div>أغسطس 23, 2026</div><div>اخر موعد للعطاء</div><div>نوفمبر 17, 2026</div>
<div>تاريخ الإجتماع التمهيدي</div><div>سبتمبر 27, 2026</div>
<div>الرقم</div><div>2147428</div><div>الجهة</div><div>شركة نفط الكويت</div>
<div>الموضوع</div><div>تقديم خدمات الامن السيبراني المدارة</div>
<div>تاريخ الطلب</div><div>أغسطس 23, 2026</div><div>اخر موعد للعطاء</div><div>نوفمبر 17, 2026</div>
</body></html>
"""

PAGE_NON_CONSTRUCTION = """
<html><body><h1>المناقصات المطروحة</h1>
<div>الرقم</div><div>2147428</div><div>الجهة</div><div>شركة نفط الكويت</div>
<div>الموضوع</div><div>تقديم خدمات الامن السيبراني المدارة</div>
<div>تاريخ الطلب</div><div>أغسطس 23, 2026</div><div>اخر موعد للعطاء</div><div>نوفمبر 17, 2026</div>
</body></html>
"""

PAGE2 = """
<html><body><h1>المناقصات المطروحة</h1>
<div>الرقم</div><div>و ك م /14/2024/2025</div><div>الجهة</div><div>وزارة الكهرباء والماء والطاقة المتجددة</div>
<div>الموضوع</div><div>اعمال توريد وتركيب وصيانه خطوط هوائيه و الاعمال المدنيه المتعلقه بها</div>
<div>تاريخ الطلب</div><div>أغسطس 23, 2026</div><div>اخر موعد للعطاء</div><div>سبتمبر 22, 2026</div>
<div>تاريخ الإجتماع التمهيدي</div><div>سبتمبر 2, 2026</div>
</body></html>
"""


def test_parse_filter_normalize_native_identity_and_dates():
    rows = parse_open_tenders(PAGE1)
    assert [r.tender_no for r in rows] == ["6/2025/2026", "2147428"]
    assert is_construction_relevant(rows[0]) is True
    assert is_construction_relevant(rows[1]) is False
    records = normalize_construction_tenders(rows)
    assert len(records) == 1
    record = records[0]
    assert record["source"] == "KW_CAPT"
    assert record["signal_type"] == "TENDER"
    assert record["external_id"] == "6/2025/2026"
    assert record["source_reference"] == "6/2025/2026"
    assert record["country"] == "KWT"
    assert record["publication_date"] == "2026-08-23"
    assert record["deadline"] == "2026-11-17"
    assert record["premeeting_date"] == "2026-09-27"


def test_native_identity_survives_title_change():
    a = CAPTTender("6/2025/2026", "DGCA", "اعمال انشائية", "أغسطس 23, 2026", "نوفمبر 17, 2026")
    b = CAPTTender("6/2025/2026", "DGCA", "اعمال انشائية - تحديث", "أغسطس 23, 2026", "نوفمبر 17, 2026")
    assert normalize_tender(a)["external_id"] == normalize_tender(b)["external_id"]


class _Response:
    def __init__(self, text): self.text = text
    def raise_for_status(self): return None


class _Session:
    def __init__(self): self.urls = []
    def get(self, url, timeout, headers):
        self.urls.append(url)
        assert timeout == 7
        if "?page=2" in url: return _Response(PAGE2)
        if "?page=3" in url: return _Response(PAGE2)
        return _Response(PAGE1)


class _NonConstructionSession:
    def get(self, url, timeout, headers):
        return _Response(PAGE_NON_CONSTRUCTION)


def test_pagination_is_bounded_and_stops_on_repeat():
    session = _Session()
    rows = fetch_open_tenders(session=session, timeout=7, max_pages=5)
    assert [r.tender_no for r in rows] == ["6/2025/2026", "2147428", "و ك م /14/2024/2025"]
    assert len(session.urls) == 3
    signals = KuwaitCAPTConnector(session=_Session(), timeout=7, max_pages=5).fetch()
    assert {s["external_id"] for s in signals} == {"6/2025/2026", "و ك م /14/2024/2025"}


def test_valid_source_response_with_zero_construction_matches_is_healthy_empty():
    signals = fetch_normalized_construction_tenders(
        session=_NonConstructionSession(), timeout=7, max_pages=1
    )
    assert signals == []
    assert KuwaitCAPTConnector(
        session=_NonConstructionSession(), timeout=7, max_pages=1
    ).fetch() == []


def test_canonical_signal_store_idempotent_update():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    record = normalize_construction_tenders(parse_open_tenders(PAGE1))[0]
    assert persist_signal_records(conn, [record], observed_at="2026-08-25T00:00:00+00:00", expected_source="KW_CAPT") == 1
    updated = dict(record, title=record["title"] + " updated")
    assert persist_signal_records(conn, [updated], observed_at="2026-08-25T01:00:00+00:00", expected_source="KW_CAPT") == 1
    stored = get_signal_record(conn, "KW_CAPT", "6/2025/2026", "TENDER")
    assert stored["title"].endswith("updated")
    assert stored["first_observed"] == "2026-08-25T00:00:00+00:00"
    assert stored["last_observed"] == "2026-08-25T01:00:00+00:00"


def test_deadline_before_request_fails_closed():
    tender = CAPTTender("x/2026", "Buyer", "اعمال انشائية", "أغسطس 23, 2026", "يوليو 1, 2026")
    with pytest.raises(KuwaitCAPTSourceError, match="predates"):
        normalize_tender(tender)


class _FailingSession:
    def get(self, *args, **kwargs): raise requests.Timeout("publisher timeout")


def test_transport_failure_is_error_not_zero():
    with pytest.raises(KuwaitCAPTSourceError, match="fetch failed"):
        fetch_open_tenders(session=_FailingSession(), timeout=1, max_pages=1)


def test_changed_contract_is_error_not_zero():
    with pytest.raises(KuwaitCAPTSourceError):
        parse_open_tenders("<html><body>no tenders</body></html>")
