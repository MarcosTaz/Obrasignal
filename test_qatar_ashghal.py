import sqlite3

import pytest
import requests

from qatar_ashghal import (
    MAX_HTML_BYTES,
    AshghalSourceError,
    AshghalTender,
    fetch_open_tenders,
    is_construction_relevant,
    normalize_construction_tenders,
    normalize_tender,
    parse_open_tenders,
)
from signal_store import get_signal_record, persist_signal_records


FIXTURE = """
<html><body><h2>Open Tenders (2)</h2><table>
<tr><th>Tender No.</th><th>Type</th><th>Tender Title</th><th>Issuing Date</th><th>Closing Date</th><th>Category</th></tr>
<tr><td>PWA/GTC/17/2026</td><td>GTC</td><td>D&amp;B Stormwater Drainage Networks at Education City – Phase 1</td><td>30 July 2026</td><td>22 September 2026</td><td></td></tr>
<tr><td>PWA/STC/32/2026</td><td>STC</td><td>Call Off Agreement for IT Security Operations &amp; Maintenance</td><td>13 August 2026</td><td>13 September 2026</td><td></td></tr>
</table></body></html>
"""


def test_parse_filter_normalize_uses_publisher_identity():
    rows = parse_open_tenders(FIXTURE)
    assert len(rows) == 2
    assert rows[0].tender_no == "PWA/GTC/17/2026"
    assert is_construction_relevant(rows[0]) is True
    assert is_construction_relevant(rows[1]) is False

    normalized = normalize_construction_tenders(rows)
    assert len(normalized) == 1
    record = normalized[0]
    assert record["source"] == "QA_ASHGHAL"
    assert record["signal_type"] == "TENDER"
    assert record["external_id"] == "PWA/GTC/17/2026"
    assert record["source_reference"] == "PWA/GTC/17/2026"
    assert record["country"] == "QAT"
    assert record["publication_date"] == "2026-07-30"
    assert record["deadline"] == "2026-09-22"
    assert record["construction_relevant"] is True
    assert record["coverage_scope"].startswith("LIMITED_HIGH_VALUE_SLICE")


def test_classifier_uses_token_boundaries_not_substrings():
    false_positive = AshghalTender("PWA/STC/77/2026", "STC", "Corporate technology roadmap and broadband services", "13 August 2026", "13 September 2026")
    true_positive = AshghalTender("PWA/STC/78/2026", "STC", "Road maintenance works package", "13 August 2026", "13 September 2026")
    assert is_construction_relevant(false_positive) is False
    assert is_construction_relevant(true_positive) is True


def test_identity_is_stable_across_title_case_changes():
    base = AshghalTender("PWA/GTC/17/2026", "GTC", "Roads and Infrastructure Works", "30 July 2026", "22 September 2026")
    changed = AshghalTender("PWA/GTC/17/2026", "GTC", "ROADS AND INFRASTRUCTURE WORKS - UPDATED", "30 July 2026", "22 September 2026")
    assert normalize_tender(base)["external_id"] == normalize_tender(changed)["external_id"]


def test_chronology_violation_is_source_error():
    bad = AshghalTender("PWA/GTC/99/2026", "GTC", "Road works", "22 September 2026", "30 July 2026")
    with pytest.raises(AshghalSourceError, match="closing date precedes issuing date"):
        normalize_tender(bad)


def test_canonical_signal_store_idempotent_update():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    record = normalize_construction_tenders(parse_open_tenders(FIXTURE))[0]
    assert persist_signal_records(conn, [record], observed_at="2026-08-25T00:00:00+00:00", expected_source="QA_ASHGHAL") == 1
    updated = dict(record, title=record["title"] + " UPDATED")
    assert persist_signal_records(conn, [updated], observed_at="2026-08-25T01:00:00+00:00", expected_source="QA_ASHGHAL") == 1
    stored = get_signal_record(conn, "QA_ASHGHAL", "PWA/GTC/17/2026", "TENDER")
    assert stored["title"].endswith("UPDATED")
    assert stored["first_observed"] == "2026-08-25T00:00:00+00:00"
    assert stored["last_observed"] == "2026-08-25T01:00:00+00:00"


def test_empty_changed_or_oversized_contract_is_error_not_zero():
    with pytest.raises(AshghalSourceError):
        parse_open_tenders("<html><body>No tender table</body></html>")
    with pytest.raises(AshghalSourceError, match="exceeds safety limit"):
        parse_open_tenders("x" * (MAX_HTML_BYTES + 1))


class _Response:
    text = FIXTURE
    def raise_for_status(self):
        return None


class _Session:
    def get(self, url, timeout, headers):
        assert url.startswith("https://www.ashghal.gov.qa/")
        assert timeout == 7
        return _Response()


def test_fetch_contract_and_timeout_are_explicit():
    rows = fetch_open_tenders(session=_Session(), timeout=7)
    assert [r.tender_no for r in rows] == ["PWA/GTC/17/2026", "PWA/STC/32/2026"]
    for invalid in (0, -1, 61, True, "7"):
        with pytest.raises(ValueError):
            fetch_open_tenders(session=_Session(), timeout=invalid)


class _FailingSession:
    def get(self, *args, **kwargs):
        raise requests.Timeout("publisher timeout")


def test_transport_failure_propagates_as_source_error():
    with pytest.raises(AshghalSourceError, match="fetch failed"):
        fetch_open_tenders(session=_FailingSession(), timeout=1)
