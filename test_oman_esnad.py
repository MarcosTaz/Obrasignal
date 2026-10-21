import sqlite3

import pytest
import requests

from oman_esnad import (
    OmanEsnadSourceError,
    UpcomingTender,
    fetch_upcoming_tenders,
    is_construction_relevant,
    normalize_construction_plans,
    normalize_upcoming,
    parse_upcoming_tenders,
)
from signal_store import get_signal_record, persist_signal_records


FIXTURE = """
<html><body><h2>Upcoming Tender</h2><table>
<tr><th>S.No.</th><th>Tender No</th><th>Tender Title</th><th>Entity</th><th>Category</th><th>Action</th></tr>
<tr><td>1.</td><td>[ 96782 ] - 2026/657/و ت ت/م ع ص-12</td><td>صيانة المواقف الخارجية لديوان عام الوزارة</td><td>وزارة التعليم</td><td>المقاولات العمرانيه والصيانة [الرابعة]</td><td></td></tr>
<tr><td>2.</td><td>[ 96901 ] - 2026/48/م و إ م/ م ر -8</td><td>توريد وتركيب الشاشات الرقمية</td><td>المركز الوطني للإحصاء والمعلومات</td><td>التوريدات [الممتازة,الأولى]</td><td></td></tr>
</table></body></html>
"""


def test_parse_filter_and_normalize_upcoming_plan():
    rows = parse_upcoming_tenders(FIXTURE)
    assert [r.internal_id for r in rows] == ["96782", "96901"]
    assert rows[0].tender_no == "2026/657/و ت ت/م ع ص-12"
    assert is_construction_relevant(rows[0]) is True
    assert is_construction_relevant(rows[1]) is False
    records = normalize_construction_plans(rows)
    assert len(records) == 1
    record = records[0]
    assert record["source"] == "OM_ESNAD"
    assert record["signal_type"] == "PROCUREMENT_PLAN"
    assert record["external_id"] == "96782"
    assert record["source_reference"] == "2026/657/و ت ت/م ع ص-12"
    assert record["country"] == "OMN"
    assert record["publication_date"] is None
    assert record["deadline"] is None
    assert record["coverage_scope"].startswith("LIMITED_HIGH_VALUE_SLICE")


def test_category_can_prove_physical_works_even_when_title_is_generic():
    row = UpcomingTender("96772", "2026/33/و ق ع/ م ر -32", "خدمات الصيانة", "وزارة القوى العاملة", "المقاولات العمرانيه والصيانة [الرابعة]")
    assert is_construction_relevant(row) is True


def test_supply_installation_does_not_become_construction_without_physical_works_evidence():
    row = UpcomingTender("96901", "2026/48/test", "توريد وتركيب الشاشات الرقمية", "Entity", "التوريدات")
    assert is_construction_relevant(row) is False


def test_native_internal_identity_survives_title_change():
    a = UpcomingTender("96782", "2026/657/test", "صيانة المواقف الخارجية", "Entity", "المقاولات العمرانيه والصيانة")
    b = UpcomingTender("96782", "2026/657/test", "صيانة المواقف الخارجية - تحديث", "Entity", "المقاولات العمرانيه والصيانة")
    assert normalize_upcoming(a)["external_id"] == normalize_upcoming(b)["external_id"]


def test_canonical_signal_store_idempotent_update():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    record = normalize_construction_plans(parse_upcoming_tenders(FIXTURE))[0]
    assert persist_signal_records(conn, [record], observed_at="2026-08-25T00:00:00+00:00", expected_source="OM_ESNAD") == 1
    updated = dict(record, title=record["title"] + " updated")
    assert persist_signal_records(conn, [updated], observed_at="2026-08-25T01:00:00+00:00", expected_source="OM_ESNAD") == 1
    stored = get_signal_record(conn, "OM_ESNAD", "96782", "PROCUREMENT_PLAN")
    assert stored["title"].endswith("updated")
    assert stored["first_observed"] == "2026-08-25T00:00:00+00:00"
    assert stored["last_observed"] == "2026-08-25T01:00:00+00:00"


class _Response:
    text = FIXTURE
    def raise_for_status(self):
        return None


class _Session:
    def get(self, url, timeout, headers):
        assert "viewFlag=UpcomingTenders" in url
        assert timeout == 7
        return _Response()


def test_fetch_contract_is_public_and_bounded():
    rows = fetch_upcoming_tenders(session=_Session(), timeout=7)
    assert len(rows) == 2


class _FailingSession:
    def get(self, *args, **kwargs):
        raise requests.Timeout("publisher timeout")


def test_transport_failure_is_error_not_zero():
    with pytest.raises(OmanEsnadSourceError, match="fetch failed"):
        fetch_upcoming_tenders(session=_FailingSession(), timeout=1)


def test_changed_contract_is_error_not_zero():
    with pytest.raises(OmanEsnadSourceError):
        parse_upcoming_tenders("<html><body>no upcoming table</body></html>")
