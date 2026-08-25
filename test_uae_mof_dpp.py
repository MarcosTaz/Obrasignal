import sqlite3

import pytest
import requests

from signal_store import get_signal_record, persist_signal_records
from uae_mof_dpp import (
    FederalOpportunity,
    UAEMoFDPPConnector,
    UAEMoFSourceError,
    fetch_current_opportunities,
    is_construction_relevant,
    normalize_construction_opportunities,
    normalize_opportunity,
    parse_opportunities,
)


PAGE1 = """
<html><body><h1>Current Business Opportunities</h1><h2>Open tenders</h2><table>
<tr><th>RFQ Number</th><th>Entity Name</th><th>Title</th><th>Open Date</th><th>Close Date</th><th>Link</th></tr>
<tr><td>12051</td><td>Ministry of Education - (109/16894)</td><td>DESIGN AND BUILD CONTRACT FOR SPORTS FIELDS AND THEIR COMPONENTS</td><td>18/08/2026 12:00:00 AM</td><td>08/09/2026 4:00:00 PM</td><td><a href="https://procurement.gov.ae/rfq/12051">Click here</a></td></tr>
<tr><td>12082</td><td>Other Federal Spending - (198/198-996)</td><td>Inspection, Verification, Tagging and Valuation of the Federal Government Infrastructure Assets</td><td>18/08/2026 11:30:00 AM</td><td>08/09/2026 11:00:00 PM</td><td><a href="https://procurement.gov.ae/rfq/12082">Click here</a></td></tr>
</table></body></html>
"""

PAGE2 = """
<html><body><h1>Current Business Opportunities</h1><h2>Open tenders</h2><table>
<tr><th>RFQ Number</th><th>Entity Name</th><th>Title</th><th>Open Date</th><th>Close Date</th><th>Link</th></tr>
<tr><td>11995</td><td>Ministry of Education - (109/16894)</td><td>CCTV &amp; Access Control Systems (ACS) for MOE</td><td>11/08/2026 12:00:00 AM</td><td>10/09/2026 3:00:00 PM</td><td><a href="https://procurement.gov.ae/rfq/11995">Click here</a></td></tr>
</table></body></html>
"""


def test_parse_and_strong_construction_filter():
    rows = parse_opportunities(PAGE1)
    assert [r.rfq_number for r in rows] == ["12051", "12082"]
    assert rows[0].detail_url == "https://procurement.gov.ae/rfq/12051"
    assert is_construction_relevant(rows[0]) is True
    # Infrastructure asset valuation is commercially adjacent but not physical works.
    assert is_construction_relevant(rows[1]) is False
    signals = normalize_construction_opportunities(rows)
    assert [s["external_id"] for s in signals] == ["12051"]
    signal = signals[0]
    assert signal["signal_type"] == "TENDER"
    assert signal["source"] == "AE_MOF_DPP"
    assert signal["country"] == "ARE"
    assert signal["publication_date"] == "2026-08-18"
    assert signal["published_at"] == "2026-08-18T00:00:00"
    assert signal["deadline"] == "2026-09-08T16:00:00"


def test_identity_is_rfq_not_title():
    base = FederalOpportunity("12051", "MOE", "Design and Build Contract", "18/08/2026 12:00:00 AM", "08/09/2026 4:00:00 PM")
    changed = FederalOpportunity("12051", "MOE", "Design and Build Contract UPDATED", "18/08/2026 12:00:00 AM", "08/09/2026 4:00:00 PM")
    assert normalize_opportunity(base)["external_id"] == normalize_opportunity(changed)["external_id"] == "12051"


class _Response:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        return None


class _Session:
    def __init__(self):
        self.urls = []
    def get(self, url, timeout, headers):
        self.urls.append(url)
        assert timeout == 7
        if "mof-dpp-page=2" in url:
            return _Response(PAGE2)
        if "mof-dpp-page=3" in url:
            return _Response(PAGE2)  # repeated publisher page -> bounded stop
        return _Response(PAGE1)


def test_pagination_deduplicates_and_stops_on_repeated_page():
    session = _Session()
    rows = fetch_current_opportunities(session=session, timeout=7, max_pages=5)
    assert [r.rfq_number for r in rows] == ["12051", "12082", "11995"]
    assert len(session.urls) == 3
    connector = UAEMoFDPPConnector(session=_Session(), timeout=7, max_pages=5)
    assert [r["external_id"] for r in connector.fetch()] == ["12051"]


def test_canonical_signal_store_idempotent_update():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    record = normalize_construction_opportunities(parse_opportunities(PAGE1))[0]
    assert persist_signal_records(conn, [record], observed_at="2026-08-25T00:00:00+00:00", expected_source="AE_MOF_DPP") == 1
    updated = dict(record, title=record["title"] + " UPDATED")
    assert persist_signal_records(conn, [updated], observed_at="2026-08-25T01:00:00+00:00", expected_source="AE_MOF_DPP") == 1
    stored = get_signal_record(conn, "AE_MOF_DPP", "12051", "TENDER")
    assert stored["title"].endswith("UPDATED")
    assert stored["first_observed"] == "2026-08-25T00:00:00+00:00"
    assert stored["last_observed"] == "2026-08-25T01:00:00+00:00"


def test_close_before_open_fails_closed():
    row = FederalOpportunity("12051", "MOE", "Construction works", "18/08/2026 12:00:00 AM", "01/08/2026 4:00:00 PM")
    with pytest.raises(UAEMoFSourceError, match="predates"):
        normalize_opportunity(row)


class _FailingSession:
    def get(self, *args, **kwargs):
        raise requests.Timeout("publisher timeout")


def test_transport_failure_is_error_not_zero():
    with pytest.raises(UAEMoFSourceError, match="fetch failed"):
        fetch_current_opportunities(session=_FailingSession(), timeout=1, max_pages=1)


def test_changed_contract_is_error_not_zero():
    with pytest.raises(UAEMoFSourceError):
        parse_opportunities("<html><body>No opportunities</body></html>")
