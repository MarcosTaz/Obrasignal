from datetime import datetime, timezone
import json

import pytest

from switzerland_simap import (
    SIMAPCursor,
    SIMAPConnector,
    SIMAP_DETAIL,
    SIMAP_HEADER,
    SIMAP_SEARCH,
    normalize_simap_target,
)


class Response:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class Session:
    def __init__(self, *, search_pages=None, headers=None, details=None):
        self.search_pages = search_pages or {}
        self.headers = headers or {}
        self.details = details or {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        params_list = list(params or [])
        self.calls.append((url, params_list))
        if url == SIMAP_SEARCH:
            token = dict(params_list).get("lastItem")
            return Response(self.search_pages.get(token, {"projects": [], "pagination": {}}))
        for project_id, payload in self.headers.items():
            if url == SIMAP_HEADER.format(project_id=project_id):
                return Response(payload)
        for (project_id, publication_id), payload in self.details.items():
            if url == SIMAP_DETAIL.format(project_id=project_id, publication_id=publication_id):
                return Response(payload)
        return Response({"error": "not found"}, status=404)


def search_row(project_id="p1", *, publication_id="pub1", corrected=False, lots=None):
    return {
        "id": project_id,
        "projectNumber": "40001",
        "projectSubType": "construction",
        "projectType": "tender",
        "processType": "open",
        "pubType": "tender",
        "publicationId": publication_id,
        "publicationDate": "2026-08-24",
        "publicationNumber": "40001-01",
        "corrected": corrected,
        "title": {"en": "Road works"},
        "procOfficeName": {"en": "City works office"},
        "orderAddress": {"city": {"en": "Bern"}, "postalCode": "3000", "cantonId": "BE", "countryId": "CH"},
        "lots": lots or [],
    }


def publication(pub_id="pub1", *, pub_type="tender", deadline="2026-09-10T10:00:00+02:00", corrected=False):
    dates = {"publicationDate": "2026-08-24", "pubType": pub_type}
    if deadline is not None:
        dates["offerDeadline"] = deadline
    return {
        "id": pub_id,
        "pubType": pub_type,
        "projectType": "tender",
        "projectSubType": "construction",
        "processType": "open",
        "publicationNumber": "40001-01",
        "corrected": corrected,
        "title": {"en": "Road works"},
        "dates": dates,
    }


def header_without(project_id="p1", *, latest=None):
    return {
        "id": project_id,
        "projectNumber": "40001",
        "projectType": "tender",
        "projectSubType": "construction",
        "processType": "open",
        "lotsType": "without",
        "latestPublication": latest or publication(),
        "lots": [],
    }


def detail_without(*, cpv="45000000", cpc=None, corrected=False):
    procurement = {
        "orderType": "construction",
        "constructionType": "execution",
        "orderAddress": {"city": {"en": "Bern"}, "postalCode": "3000", "cantonId": "BE", "countryId": "CH"},
    }
    if cpv is not None:
        procurement["cpvCode"] = {"code": cpv}
    if cpc is not None:
        procurement["cpcCode"] = {"code": cpc}
    return {
        "project-info": {"procOfficeName": {"en": "City works office"}, "contactEmail": "secret@example.test"},
        "procurement": procurement,
        "correction": {"correctionDiffKeys": ["dates.offerDeadline"]} if corrected else {},
    }


def decode(cursor):
    return SIMAPCursor.decode(cursor)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def test_structured_search_pages_with_opaque_lastitem_and_tracks_actionable_projects():
    p1 = search_row("p1", publication_id="pub1")
    p2 = search_row("p2", publication_id="pub2")
    session = Session(
        search_pages={
            None: {"projects": [p1], "pagination": {"lastItem": "20260824|40001", "itemsPerPage": 20}},
            "20260824|40001": {"projects": [p2], "pagination": {"lastItem": None, "itemsPerPage": 20}},
        },
        headers={
            "p1": header_without("p1", latest=publication("pub1")),
            "p2": header_without("p2", latest=publication("pub2")),
        },
        details={
            ("p1", "pub1"): detail_without(cpv="45000000"),
            ("p2", "pub2"): detail_without(cpv="45200000"),
        },
    )
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(now=NOW)

    assert {row["external_id"] for row in rows} == {"p1", "p2"}
    assert all(row["is_actionable"] is True for row in rows)
    decoded = decode(cursor)
    assert decoded.observed_through == "2026-08-24"
    assert decoded.tracked_targets == ("p1", "p2")

    search_calls = [params for url, params in session.calls if url == SIMAP_SEARCH]
    assert len(search_calls) == 2
    first = search_calls[0]
    assert ("projectSubTypes", "construction") in first
    assert ("newestPubTypes", "tender") in first
    assert not any(key in {"search", "lang"} for key, _value in first)
    assert ("lastItem", "20260824|40001") in search_calls[1]


def test_lot_level_normalization_uses_stable_target_and_native_taxonomies():
    lot = {"id": "lot-1", "lotNumber": 1, "title": {"fr": "Génie civil"}, "projectSubType": "construction"}
    header = {
        "id": "p-lot",
        "projectNumber": "41000",
        "projectSubType": "construction",
        "processType": "open",
        "lotsType": "with",
        "lots": [{**lot, "latestPublication": publication("pub-lot")}],
    }
    detail = {
        "project-info": {"procOfficeName": {"fr": "Office cantonal"}},
        "procurement": {"orderType": "construction"},
        "lots": [{
            "id": "lot-1",
            "projectSubType": "construction",
            "constructionType": "execution",
            "cpvCode": {"code": "45233120"},
            "cpcCode": {"code": "53211"},
            "bkpCodes": [{"code": "411"}],
            "orderAddress": {"city": {"fr": "Lausanne"}, "cantonId": "VD", "countryId": "CH"},
        }],
    }
    item = normalize_simap_target(
        header,
        publication("pub-lot"),
        detail=detail,
        discovery=search_row("p-lot", publication_id="pub-lot"),
        lot=lot,
        now=NOW,
    )
    assert item["external_id"] == "p-lot:lot:lot-1"
    assert item["cpv"] == "45233120"
    assert item["taxonomy"] == "CPV"
    assert item["category_code"] == "45233120"
    assert item["cpc_codes"] == ["53211"]
    assert item["bkp_codes"] == ["411"]
    assert item["lot_id"] == "lot-1"
    assert item["contract_type"] == "execution"
    assert item["place"] == "Lausanne | VD | CH"


def test_non_construction_lot_is_not_normalized():
    header = {"id": "p1", "projectSubType": "construction"}
    lot = {"id": "lot-service", "projectSubType": "service"}
    assert normalize_simap_target(
        header,
        publication(),
        detail={},
        lot=lot,
        now=NOW,
    ) is None


def test_legal_release_gate_blocks_before_0800_zurich_then_opens():
    header = header_without()
    pub = publication()
    discovery = search_row()
    detail = detail_without()

    before = normalize_simap_target(
        header, pub, detail=detail, discovery=discovery,
        now=datetime(2026, 8, 24, 5, 59, tzinfo=timezone.utc),
    )
    at_gate = normalize_simap_target(
        header, pub, detail=detail, discovery=discovery,
        now=datetime(2026, 8, 24, 6, 0, tzinfo=timezone.utc),
    )

    assert before["is_actionable"] is False
    assert before["_lifecycle_only"] is True
    assert before["lifecycle_status"] == "legal_release_pending"
    assert before["reuse_available_from"] == "2026-08-24T08:00:00+02:00"
    assert at_gate["is_actionable"] is True
    assert "_lifecycle_only" not in at_gate


def test_corrected_tender_uses_current_deadline_and_remains_actionable():
    pub = publication("pub-corrected", deadline="2026-09-18T23:59:00+02:00", corrected=True)
    item = normalize_simap_target(
        header_without(latest=pub),
        pub,
        detail=detail_without(corrected=True),
        discovery=search_row(publication_id="pub-corrected", corrected=True),
        now=NOW,
    )
    assert item["is_actionable"] is True
    assert item["corrected"] is True
    assert item["deadline"] == "2026-09-18T23:59:00+02:00"
    assert item["correction_diff_keys"] == ["dates.offerDeadline"]


@pytest.mark.parametrize(
    ("pub_type", "expected"),
    [("revocation", "revoked"), ("abandonment", "abandoned"), ("award_tender", "award_tender")],
)
def test_terminal_latest_publication_becomes_lifecycle_only(pub_type, expected):
    pub = publication("terminal", pub_type=pub_type, deadline=None)
    item = normalize_simap_target(header_without(latest=pub), pub, now=NOW)
    assert item["is_actionable"] is False
    assert item["_lifecycle_only"] is True
    assert item["lifecycle_status"] == expected


def test_tracked_project_is_rehydrated_outside_discovery_window():
    session = Session(
        search_pages={None: {"projects": [], "pagination": {}}},
        headers={"p1": header_without("p1", latest=publication("pub1"))},
        details={("p1", "pub1"): detail_without()},
    )
    watermark = SIMAPCursor("2026-08-20", ("p1",)).encode()
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(watermark=watermark, now=NOW)
    assert [row["external_id"] for row in rows] == ["p1"]
    assert rows[0]["is_actionable"] is True
    assert decode(cursor).tracked_targets == ("p1",)


def test_disappearing_tracked_lot_emits_tombstone_and_leaves_tracking():
    header = {
        "id": "p1",
        "projectNumber": "1",
        "projectSubType": "construction",
        "processType": "open",
        "lotsType": "with",
        "lots": [{
            "id": "new-service",
            "projectSubType": "service",
            "latestPublication": publication("service-pub"),
        }],
    }
    session = Session(
        search_pages={None: {"projects": [], "pagination": {}}},
        headers={"p1": header},
    )
    old = "p1:lot:old-construction"
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(
        watermark=SIMAPCursor("2026-08-20", (old,)).encode(),
        now=NOW,
    )
    assert rows == [{
        "source": "CH_SIMAP",
        "external_id": old,
        "country": "CHE",
        "source_reference": "p1",
        "source_status": "missing_from_current_header",
        "signal_type": "TENDER",
        "is_actionable": False,
        "lifecycle_status": "inactive",
        "lifecycle_reason": "previously tracked SIMAP target is absent from the current project header",
        "_lifecycle_only": True,
    }]
    assert decode(cursor).tracked_targets == ()


def test_expired_tracked_tender_emits_tombstone_and_stops_tracking():
    expired = publication("pub1", deadline="2026-08-24T10:00:00+02:00")
    session = Session(
        search_pages={None: {"projects": [], "pagination": {}}},
        headers={"p1": header_without("p1", latest=expired)},
        details={("p1", "pub1"): detail_without()},
    )
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(
        watermark=SIMAPCursor("2026-08-20", ("p1",)).encode(),
        now=NOW,
    )
    assert rows[0]["lifecycle_status"] == "deadline_expired"
    assert rows[0]["_lifecycle_only"] is True
    assert decode(cursor).tracked_targets == ()


def test_missing_deadline_stays_tracked_for_lifecycle_followup():
    missing = publication("pub1", deadline=None)
    session = Session(
        search_pages={None: {"projects": [search_row()], "pagination": {}}},
        headers={"p1": header_without("p1", latest=missing)},
        details={("p1", "pub1"): detail_without()},
    )
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(now=NOW)
    assert rows[0]["lifecycle_status"] == "deadline_missing"
    assert decode(cursor).tracked_targets == ("p1",)


def test_terminal_tracked_project_does_not_hydrate_detail():
    revoked = publication("rev1", pub_type="revocation", deadline=None)
    session = Session(
        search_pages={None: {"projects": [], "pagination": {}}},
        headers={"p1": header_without("p1", latest=revoked)},
    )
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(
        watermark=SIMAPCursor("2026-08-20", ("p1",)).encode(),
        now=NOW,
    )
    assert rows[0]["lifecycle_status"] == "revoked"
    assert not [url for url, _params in session.calls if "publication-details" in url]
    assert decode(cursor).tracked_targets == ()


def test_shared_publication_for_multiple_lots_is_hydrated_once():
    lots = [
        {"id": "lot1", "lotNumber": 1, "projectSubType": "construction", "latestPublication": publication("pub-shared")},
        {"id": "lot2", "lotNumber": 2, "projectSubType": "construction", "latestPublication": publication("pub-shared")},
    ]
    header = {
        "id": "p1",
        "projectNumber": "40046",
        "projectSubType": "construction",
        "processType": "open",
        "lotsType": "with",
        "lots": lots,
    }
    detail = {
        "procurement": {},
        "lots": [
            {"id": "lot1", "projectSubType": "construction", "cpvCode": {"code": "45100000"}},
            {"id": "lot2", "projectSubType": "construction", "cpvCode": {"code": "45200000"}},
        ],
    }
    session = Session(
        search_pages={None: {"projects": [search_row()], "pagination": {}}},
        headers={"p1": header},
        details={("p1", "pub-shared"): detail},
    )
    rows, cursor = SIMAPConnector(session=session).fetch_incremental(now=NOW)
    assert {row["external_id"] for row in rows} == {"p1:lot:lot1", "p1:lot:lot2"}
    detail_calls = [url for url, _params in session.calls if "publication-details" in url]
    assert len(detail_calls) == 1
    assert set(decode(cursor).tracked_targets) == {"p1:lot:lot1", "p1:lot:lot2"}


def test_cpc_is_preserved_without_fake_cpv():
    item = normalize_simap_target(
        header_without(),
        publication(),
        detail=detail_without(cpv=None, cpc="53211"),
        discovery=search_row(),
        now=NOW,
    )
    assert item["cpv"] == ""
    assert item["taxonomy"] == "CPC"
    assert item["category_code"] == "53211"
    assert item["cpc_codes"] == ["53211"]


def test_curated_output_does_not_persist_contact_pii_or_raw_detail():
    item = normalize_simap_target(
        header_without(),
        publication(),
        detail=detail_without(),
        discovery=search_row(),
        now=NOW,
    )
    encoded = json.dumps(item)
    assert "secret@example.test" not in encoded
    assert "project-info" not in item
    assert "raw" not in item


def test_page_limit_and_repeated_token_fail_without_cursor():
    first = {"projects": [search_row()], "pagination": {"lastItem": "token-1"}}
    session = Session(search_pages={None: first})
    with pytest.raises(RuntimeError, match="cursor not advanced"):
        SIMAPConnector(session=session, max_pages_per_sync=1).fetch_incremental(now=NOW)

    repeated = Session(search_pages={
        None: first,
        "token-1": {"projects": [], "pagination": {"lastItem": "token-1"}},
    })
    with pytest.raises(RuntimeError, match="repeated lastItem"):
        SIMAPConnector(session=repeated, max_pages_per_sync=3).fetch_incremental(now=NOW)


def test_project_and_detail_hydration_limits_are_hard_stops():
    two_projects = Session(search_pages={
        None: {"projects": [search_row("p1"), search_row("p2")], "pagination": {}}
    })
    with pytest.raises(RuntimeError, match="project hydrations.*cursor not advanced"):
        SIMAPConnector(session=two_projects, max_project_hydrations_per_sync=1).fetch_incremental(now=NOW)

    lots = [
        {"id": "lot1", "projectSubType": "construction", "latestPublication": publication("pub1")},
        {"id": "lot2", "projectSubType": "construction", "latestPublication": publication("pub2")},
    ]
    session = Session(
        search_pages={None: {"projects": [search_row("p1")], "pagination": {}}},
        headers={"p1": {"id": "p1", "projectSubType": "construction", "lotsType": "with", "lots": lots}},
    )
    with pytest.raises(RuntimeError, match="publication hydrations.*cursor not advanced"):
        SIMAPConnector(session=session, max_detail_hydrations_per_sync=1).fetch_incremental(now=NOW)


def test_cursor_is_backward_compatible_with_missing_tracking_but_rejects_corruption_and_future():
    legacy = SIMAPCursor.decode('{"observed_through":"2026-08-20"}')
    assert legacy.tracked_targets == ()

    with pytest.raises(RuntimeError, match="invalid SIMAP cursor"):
        SIMAPCursor.decode("not-json")

    session = Session(search_pages={None: {"projects": [], "pagination": {}}})
    future = SIMAPCursor("2026-08-25", ()).encode()
    with pytest.raises(RuntimeError, match="invalid/future"):
        SIMAPConnector(session=session).fetch_incremental(watermark=future, now=NOW)


def test_malformed_search_fails_instead_of_advancing_cursor():
    session = Session(search_pages={None: {"projects": "not-a-list", "pagination": {}}})
    with pytest.raises(RuntimeError, match="cursor not advanced"):
        SIMAPConnector(session=session).fetch_incremental(now=NOW)
