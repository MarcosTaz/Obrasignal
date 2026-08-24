from datetime import datetime, timezone
import json

import pytest
import requests

from netherlands_tenderned import (
    BASE,
    TenderNedCursor,
    TenderNedPublicConnector,
)


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, pages=None, details=None):
        self.pages = pages or {}
        self.details = details or {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params))
        if url == BASE:
            page = int((params or {}).get("page", 0))
            return self.pages.get(page, FakeResponse({"content": [], "totalElements": 0, "number": page, "size": int((params or {}).get("size", 100))}))
        pid = url.rsplit("/", 1)[-1]
        return self.details.get(pid, FakeResponse({}, 404))


def summary(pid, day, *, works=True):
    return {
        "publicatieId": str(pid),
        "publicatieDatum": day,
        "typeOpdracht": {"code": "W" if works else "D", "omschrijving": "Werken" if works else "Diensten"},
    }


def detail(
    pid,
    kenmerk,
    *,
    published="2026-08-24T17:26:16.894477",
    deadline="2026-10-13T10:00:00",
    works=True,
    announcement="AAO",
    status="AAN",
    awarded=False,
    completed=False,
    early=False,
    title="Herinrichting Dukaton Mijdrecht",
):
    row = {
        "publicatieId": int(pid),
        "kenmerk": int(kenmerk),
        "aanbestedingNaam": title,
        "opdrachtgeverNaam": "Gemeente De Ronde Venen",
        "opdrachtBeschrijving": "Reconstruction works",
        "publicatieDatum": published,
        "typePublicatie": "Vrijwillige aankondiging van een opdracht",
        "publicatieCode": "EFE3",
        "typeOpdrachtCode": {"code": "W" if works else "D", "omschrijving": "Werken" if works else "Diensten"},
        "procedureCode": {"code": "OPE", "omschrijving": "Openbaar"},
        "aankondigingCode": {"code": announcement, "omschrijving": "Aankondiging opdracht"},
        "aanbestedingStatus": status,
        "cpvCodes": [
            {"code": "45233100-0", "omschrijving": "Bouwwerkzaamheden voor hoofdwegen en wegen", "isHoofdOpdracht": True},
            {"code": "45112000-5", "omschrijving": "Graafwerkzaamheden", "isHoofdOpdracht": False},
        ],
        "nutsCodes": [{"code": "NL35", "omschrijving": "Utrecht"}],
        "isGegund": awarded,
        "afgerondeAanbesteding": completed,
        "isVroegtijdigBeeindigd": early,
        "nationaalOfEuropeesCode": {"code": "NL", "omschrijving": "Nationaal"},
        "juridischKaderCode": {"code": "ARW2012", "omschrijving": "ARW 2016"},
        "isDigitaalInschrijvenMogelijk": True,
        "referentieNummer": "REF-1",
        # Deliberate fields that production must not preserve wholesale.
        "contactPersoon": {"naam": "Private Person", "email": "private@example.invalid"},
    }
    if deadline is not None:
        row["sluitingsDatum"] = deadline
    return row


def page(rows, *, number=0, size=100, total=None):
    return FakeResponse({
        "content": rows,
        "totalElements": len(rows) if total is None else total,
        "totalPages": 1,
        "number": number,
        "numberOfElements": len(rows),
        "size": size,
        "first": number == 0,
        "last": False,
    })


def connector_for(rows, details, *, second_rows=None, total=None, **kwargs):
    second_rows = second_rows if second_rows is not None else [summary(1, "2026-06-01", works=False)]
    total = total if total is not None else len(rows) + len(second_rows)
    session = FakeSession(
        pages={
            0: page(rows, number=0, total=total),
            1: page(second_rows, number=1, total=total),
        },
        details={str(k): FakeResponse(v) for k, v in details.items()},
    )
    return TenderNedPublicConnector(session=session, initial_lookback_days=45, **kwargs), session


def test_open_works_uses_kenmerk_as_identity_and_native_cpv_deadline():
    client, _ = connector_for(
        [summary(437179, "2026-08-24")],
        {437179: detail(437179, 607904)},
    )
    rows, cursor = client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "NL_TENDERNED"
    assert row["external_id"] == "607904"
    assert row["source_reference"] == "437179"
    assert row["contract_type"] == "works"
    assert row["cpv"] == "45233100-0"
    assert row["cpv_codes"] == ["45233100-0", "45112000-5"]
    assert row["deadline"] == "2026-10-13T08:00:00Z"
    assert row["place"] == "Utrecht"
    assert row["is_actionable"] is True
    decoded = TenderNedCursor.decode(cursor)
    assert "607904" in decoded.tracked


def test_non_works_summary_is_not_hydrated():
    client, session = connector_for(
        [summary(10, "2026-08-24", works=False), summary(11, "2026-08-24", works=True)],
        {11: detail(11, 501)},
    )
    rows, _ = client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert [row["external_id"] for row in rows] == ["501"]
    detail_calls = [url for url, _ in session.calls if url != BASE]
    assert detail_calls == [f"{BASE}/11"]


def test_rectification_replaces_same_kenmerk_and_extends_deadline():
    first = detail(100, 900, deadline="2026-09-01T10:00:00", published="2026-08-20T10:00:00")
    rect = detail(120, 900, deadline="2026-10-01T12:00:00", published="2026-08-24T12:00:00", announcement="REC")
    client, _ = connector_for(
        [summary(120, "2026-08-24"), summary(100, "2026-08-20")],
        {100: first, 120: rect},
    )
    rows, cursor = client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["external_id"] == "900"
    assert rows[0]["source_reference"] == "120"
    assert rows[0]["announcement_code"] == "REC"
    assert rows[0]["deadline"] == "2026-10-01T10:00:00Z"
    assert TenderNedCursor.decode(cursor).tracked["900"]["publication_id"] == "120"


def test_award_closes_previously_visible_works_as_lifecycle_only():
    cursor = TenderNedCursor(
        observed_through="2026-08-23T12:00:00Z",
        tracked={"900": {**detail_state(100, 900), "was_actionable": True}},
    ).encode()
    award = detail(130, 900, published="2026-08-24T12:00:00", deadline="2026-09-01T10:00:00", announcement="AGO", status="EIN", awarded=True, completed=True)
    client, _ = connector_for([summary(130, "2026-08-24")], {130: award})
    rows, next_cursor = client.fetch_incremental(watermark=cursor, now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "awarded"
    assert rows[0]["is_actionable"] is False
    assert TenderNedCursor.decode(next_cursor).tracked == {}


def test_early_termination_closes_previously_visible_works():
    cursor = TenderNedCursor(
        observed_through="2026-08-23T12:00:00Z",
        tracked={"901": {**detail_state(101, 901), "was_actionable": True}},
    ).encode()
    ended = detail(131, 901, announcement="VBE", status="EIN", early=True, deadline=None)
    client, _ = connector_for([summary(131, "2026-08-24")], {131: ended})
    rows, _ = client.fetch_incremental(watermark=cursor, now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert rows[0]["lifecycle_status"] == "terminated"
    assert rows[0]["_lifecycle_only"] is True


def test_deadline_expiry_without_new_publication_emits_tombstone():
    state = detail_state(100, 900, deadline="2026-08-24T10:00:00")
    state["was_actionable"] = True
    cursor = TenderNedCursor(observed_through="2026-08-23T12:00:00Z", tracked={"900": state}).encode()
    client, _ = connector_for([], {})
    rows, next_cursor = client.fetch_incremental(watermark=cursor, now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["lifecycle_status"] == "deadline_elapsed"
    assert rows[0]["_lifecycle_only"] is True
    assert TenderNedCursor.decode(next_cursor).tracked == {}


def test_missing_deadline_stays_tracked_pending_for_future_rectification():
    client, _ = connector_for([summary(10, "2026-08-24")], {10: detail(10, 700, deadline=None)})
    rows, cursor = client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert rows == []
    tracked = TenderNedCursor.decode(cursor).tracked
    assert "700" in tracked
    assert tracked["700"]["was_actionable"] is False


def test_market_consultation_never_becomes_actionable_even_if_works():
    row = detail(10, 700, announcement="MAC")
    row["procedureCode"] = {"code": "MAC", "omschrijving": "Marktconsultatie"}
    client, _ = connector_for([summary(10, "2026-08-24")], {10: row})
    rows, cursor = client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    assert rows == []
    assert TenderNedCursor.decode(cursor).tracked == {}


def test_scan_rejects_total_elements_change_between_pages():
    session = FakeSession(
        pages={
            0: page([summary(10, "2026-08-24")], number=0, total=10),
            1: page([summary(9, "2026-06-01", works=False)], number=1, total=11),
        },
        details={"10": FakeResponse(detail(10, 700))},
    )
    client = TenderNedPublicConnector(session=session, initial_lookback_days=45)
    with pytest.raises(RuntimeError, match="totalElements changed"):
        client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))


def test_scan_rejects_duplicate_publication_across_pages():
    session = FakeSession(
        pages={
            0: page([summary(10, "2026-08-24")], number=0, total=2),
            1: page([summary(10, "2026-06-01")], number=1, total=2),
        },
        details={"10": FakeResponse(detail(10, 700))},
    )
    client = TenderNedPublicConnector(session=session, initial_lookback_days=45)
    with pytest.raises(RuntimeError, match="duplicate publicatieId"):
        client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))


def test_scan_rejects_non_descending_publication_dates():
    session = FakeSession(
        pages={0: page([summary(10, "2026-08-23"), summary(11, "2026-08-24")], number=0, total=2)},
    )
    client = TenderNedPublicConnector(session=session, initial_lookback_days=45)
    with pytest.raises(RuntimeError, match="not publication-date descending"):
        client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))


def test_scan_hard_stops_when_cutoff_not_reached():
    session = FakeSession(
        pages={0: page([summary(10, "2026-08-24")], number=0, total=1000)},
        details={"10": FakeResponse(detail(10, 700))},
    )
    client = TenderNedPublicConnector(session=session, initial_lookback_days=45, max_pages=1)
    with pytest.raises(RuntimeError, match="exceeds max_pages"):
        client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))


def test_page_size_above_live_validated_100_is_rejected():
    with pytest.raises(ValueError, match="maximum 100"):
        TenderNedPublicConnector(page_size=101)


def test_detail_identity_mismatch_fails_closed():
    bad = detail(11, 700)
    client, _ = connector_for([summary(10, "2026-08-24")], {10: bad})
    with pytest.raises(RuntimeError, match="detail identity mismatch"):
        client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))


def test_cursor_rejects_corrupt_and_future_values():
    with pytest.raises(RuntimeError, match="cursor JSON"):
        TenderNedCursor.decode("not-json")
    future = TenderNedCursor(observed_through="2027-01-01T00:00:00Z", tracked={}).encode()
    client, _ = connector_for([], {})
    with pytest.raises(RuntimeError, match="cursor is in the future"):
        client.fetch_incremental(watermark=future, now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))


def test_output_does_not_persist_raw_contact_payload_or_pdf():
    client, _ = connector_for([summary(10, "2026-08-24")], {10: detail(10, 700)})
    rows, _ = client.fetch_incremental(now=datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc))
    text = json.dumps(rows, ensure_ascii=False)
    assert "Private Person" not in text
    assert "private@example.invalid" not in text
    assert "contactPersoon" not in text
    assert "publicatiePdfId" not in text


def detail_state(pid, kenmerk, *, deadline="2026-10-13T10:00:00"):
    """Create cursor state through production normalization, not a hand-made schema."""
    from netherlands_tenderned import _state_from_detail

    return _state_from_detail(detail(pid, kenmerk, deadline=deadline))
