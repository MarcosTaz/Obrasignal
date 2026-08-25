import sqlite3

import pytest
import requests

from israel_gpa import (
    DETAIL_URL,
    SEARCH_URL,
    GPANotice,
    IsraelGPAConnector,
    IsraelGPASourceError,
    fetch_recent_notices,
    is_construction_relevant,
    normalize_notice,
    parse_detail,
    parse_search_serials,
)
from signal_store import get_signal_record, persist_signal_records


SEARCH_FIXTURE = """
<html><body>
<a href="/ilgstorefront/en/p/4000621193">renovation tender</a>
<a href="/ilgstorefront/en/p/4000620190">IT tender</a>
<a href="/ilgstorefront/en/p/4000621193">duplicate image link</a>
</body></html>
"""

DETAIL_CONSTRUCTION = """
<html><body>
<h1>Public Tender</h1>
<h2>מכרז 3/26 שיפוץ 2 מחלקות פנימיות בקומה 2 - המרכז הרפואי לגליל, נהריה</h2>
<h3>Publisher:</h3><h2>משרד הבריאות - אגף לתיכנון ולבינוי מוסדות רפואה</h2>
<h3>Serial:</h3><div>4000621193</div>
<h3>Status:</h3><div>פורסם</div>
<h3>Process:</h3><div>3/26</div>
<h3>Published:</h3><div>24/08/2026</div>
<h3>Updated:</h3><div>24/08/2026</div>
<h3>Deadline:</h3><div>14/10/2026 ,12:00</div>
<h2>Subjects</h2>
<div>Building and maintenance services</div>
<a>About us</a>
</body></html>
"""

DETAIL_NON_CONSTRUCTION = """
<html><body>
<h1>Public Tender</h1><h2>Internet access services</h2>
<h3>Publisher:</h3><h2>Ministry</h2>
<h3>Serial:</h3><div>4000620190</div>
<h3>Status:</h3><div>published</div>
<h3>Process:</h3><div>10-2026</div>
<h3>Published:</h3><div>27/07/2026</div>
<h3>Updated:</h3><div>23/08/2026</div>
<h3>Deadline:</h3><div>23/09/2026 12:00</div>
<h2>Subjects</h2><div>Internet services</div><a>About us</a>
</body></html>
"""


def test_search_discovery_deduplicates_native_serials():
    assert parse_search_serials(SEARCH_FIXTURE) == ["4000621193", "4000620190"]


def test_detail_parse_filter_and_normalize():
    notice = parse_detail(DETAIL_CONSTRUCTION)
    assert notice.serial == "4000621193"
    assert notice.process == "3/26"
    assert is_construction_relevant(notice) is True
    record = normalize_notice(notice)
    assert record["source"] == "IL_GPA"
    assert record["signal_type"] == "TENDER"
    assert record["external_id"] == "4000621193"
    assert record["source_reference"] == "4000621193"
    assert record["country"] == "ISR"
    assert record["publication_date"] == "2026-08-24"
    assert record["source_updated_at"] == "2026-08-24"
    assert record["deadline"] == "2026-10-14T12:00"
    assert record["coverage_scope"].startswith("LIMITED_HIGH_VALUE_SLICE")
    assert record["taxonomy"] == "IL_GPA_STRONG_TITLE_WORKS_V1"


def test_nonconstruction_notice_is_rejected_by_classifier():
    assert is_construction_relevant(parse_detail(DETAIL_NON_CONSTRUCTION)) is False


def test_subject_only_construction_label_cannot_admit_unrelated_title():
    notice = GPANotice(
        "Public Tender", "Gift vouchers for court system", "Buyer", "4000621188",
        "6/26", "published", "24/08/2026", "24/08/2026", "12/10/2026 12:00",
        ("Building and maintenance services",),
    )
    assert is_construction_relevant(notice) is False


def test_ambiguous_water_corporation_consulting_titles_are_not_works():
    consulting = GPANotice(
        "Public Tender",
        "לייעוץ, ליווי, תמיכה בהקמה וצרוף תאגידי מים וביוב",
        "Water Authority", "4000619436", "100057110", "updated",
        "12/07/2026", "13/07/2026", "24/09/2026 14:00", (),
    )
    payroll = GPANotice(
        "Public Tender",
        "לייעוץ בנושאי שכר ומבנה ארגוני בתאגידי מים וביוב ובאיגודי ערים למים וביוב",
        "Water Authority", "4000620878", "100057112", "updated",
        "16/08/2026", "24/08/2026", "22/10/2026 14:00", (),
    )
    assert is_construction_relevant(consulting) is False
    assert is_construction_relevant(payroll) is False


def test_english_word_boundaries_avoid_broadband_road_false_positive():
    notice = GPANotice("Public Tender", "Broadband services roadmap", "Buyer", "4000621199", "7/26", "published", "24/08/2026", "24/08/2026", "12/10/2026 12:00", ())
    assert is_construction_relevant(notice) is False


def test_unsupported_rfi_not_silently_reclassified_as_tender():
    notice = GPANotice("RFI", "Building study", "Buyer", "4000616577", "7854", "published", "30/04/2026", "23/08/2026", "10/09/2026 12:00", ("Building and maintenance services",))
    with pytest.raises(IsraelGPASourceError, match="unsupported GPA notice type"):
        normalize_notice(notice)


def test_deadline_before_publication_fails_closed():
    notice = GPANotice("Public Tender", "Building works", "Buyer", "4000621193", "3/26", "published", "24/08/2026", "24/08/2026", "01/05/2026", ())
    with pytest.raises(IsraelGPASourceError, match="predates publication"):
        normalize_notice(notice)


def test_canonical_signal_store_idempotent_update():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    record = normalize_notice(parse_detail(DETAIL_CONSTRUCTION))
    assert persist_signal_records(conn, [record], observed_at="2026-08-25T00:00:00+00:00", expected_source="IL_GPA") == 1
    updated = dict(record, title=record["title"] + " updated")
    assert persist_signal_records(conn, [updated], observed_at="2026-08-25T01:00:00+00:00", expected_source="IL_GPA") == 1
    stored = get_signal_record(conn, "IL_GPA", "4000621193", "TENDER")
    assert stored["title"].endswith("updated")
    assert stored["first_observed"] == "2026-08-25T00:00:00+00:00"
    assert stored["last_observed"] == "2026-08-25T01:00:00+00:00"


class _Response:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        return None


class _Session:
    def get(self, url, timeout, headers):
        assert timeout == 7
        if url == SEARCH_URL:
            return _Response(SEARCH_FIXTURE)
        if url == DETAIL_URL.format(serial="4000621193"):
            return _Response(DETAIL_CONSTRUCTION)
        if url == DETAIL_URL.format(serial="4000620190"):
            return _Response(DETAIL_NON_CONSTRUCTION)
        raise AssertionError(url)


def test_bounded_fetch_and_adapter_contract():
    notices = fetch_recent_notices(session=_Session(), timeout=7, max_details=2)
    assert [n.serial for n in notices] == ["4000621193", "4000620190"]
    records = IsraelGPAConnector(session=_Session(), timeout=7, max_details=2).fetch()
    assert [r["external_id"] for r in records] == ["4000621193"]


class _FailingSession:
    def get(self, *args, **kwargs):
        raise requests.Timeout("publisher timeout")


def test_transport_failure_is_error_not_zero():
    with pytest.raises(IsraelGPASourceError, match="fetch failed"):
        fetch_recent_notices(session=_FailingSession(), timeout=1, max_details=1)


def test_empty_or_changed_search_contract_is_error():
    with pytest.raises(IsraelGPASourceError, match="no detail links"):
        parse_search_serials("<html><body>No notices</body></html>")
