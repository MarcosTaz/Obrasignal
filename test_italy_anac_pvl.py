from datetime import datetime, timezone
import json

import pytest

from italy_anac_pvl import ANACPVLConnector, ANACPVLCursor, _notice_events


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _lot(
    cig="BCB6E8D60A",
    *,
    nature="Lavori",
    deadline="2026-09-16T15:00:00+02:00",
    cpv="Lavori di costruzione di acquedotti",
    value=25055969.06,
):
    return {
        "tipo_oggetto": "lotto",
        "cig": cig,
        "natura_principale": nature,
        "descrizione": f"Lotto {cig}",
        "cpv": cpv,
        "valore_complessivo_stimato": value,
        "documenti_di_gara_link": "https://buyer.example/tender/71",
        "luogo_nuts": "L'Aquila",
        "luogo_istat": "L'AQUILA",
        "termine_ricezione": deadline,
        "categorie": [{"codice": "OG 6", "descrizione": "ACQUEDOTTI"}],
    }


def _notice(
    notice_id="notice-1",
    *,
    procedure_id="appalto-1",
    notice_type="avviso",
    published="2026-08-24T08:00:00+00:00",
    created="2026-08-24T07:00:00+00:00",
    active=True,
    obscured=False,
    lots=None,
    top_deadline="2026-09-16T13:00:00+00:00",
):
    lots = [_lot()] if lots is None else lots
    return {
        "idAvviso": notice_id,
        "idAppalto": procedure_id,
        "codiceScheda": "P1_16",
        "codiceEform": "16",
        "tipologia": "BANDI",
        "dataScadenza": top_deadline,
        "dataPubblicazione": published,
        "dataCreazione": created,
        "tipo": notice_type,
        "attivo": active,
        "oscurato": obscured,
        "templates": [
            {
                "lingua": "it",
                "template": {
                    "metadata": {
                        "titolo": "APPALTO INTEGRATO ACQUEDOTTO",
                        "descrizione": "Esecuzione lavori acquedotto",
                        "link_eform_ted": "https://ted.europa.eu/example",
                    },
                    "sections": [
                        {
                            "name": "SEZ. A - Committente",
                            "fields": {
                                "soggetti_sa": [
                                    {"denominazione_amministrazione": "ENTE REGIONALE SERVIZIO IDRICO"}
                                ]
                            },
                        },
                        {
                            "name": "SEZ. B - Dati Generali",
                            "fields": {
                                "tipo_procedura_aggiudicazione": "Aperta",
                                "documenti_di_gara_link": "https://buyer.example/tender/71",
                            },
                        },
                        {"name": "SEZ. C - Oggetto", "items": lots},
                    ],
                },
            }
        ],
    }


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append((url, dict(params), dict(headers), timeout))
        day = params["dataPubblicazioneStart"]
        page = int(params["page"])
        return _Response(self.pages[(day, page)])


def _page(content, *, page=0, total_pages=1, total_elements=None):
    return {
        "content": content,
        "number": page,
        "totalPages": total_pages,
        "totalElements": len(content) if total_elements is None else total_elements,
        "size": 100,
        "numberOfElements": len(content),
    }


def _single_day_connector(payloads, **kwargs):
    session = _Session({("24/08/2026", 0): _page(payloads)})
    connector = ANACPVLConnector(
        session=session,
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
        **kwargs,
    )
    return connector, session


def test_publisher_native_works_lot_becomes_actionable_by_cig_without_fake_cpv_code():
    connector, _ = _single_day_connector([_notice()])
    rows, cursor = connector.fetch_incremental(now=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["external_id"] == "BCB6E8D60A"
    assert row["contract_type"] == "works"
    assert row["is_actionable"] is True
    assert row["deadline"] == "2026-09-16T13:00:00Z"
    assert row["cpv"] == ""
    assert row["cpv_codes"] == []
    assert row["anac_cpv_label"] == "Lavori di costruzione di acquedotti"
    assert row["anac_work_category_codes"] == ["OG 6"]
    assert row["source_reference"] == "notice-1"
    assert row["anac_appalto_id"] == "appalto-1"
    assert ANACPVLCursor.decode(cursor).completed_through == "2026-08-24"


def test_mixed_notice_emits_only_publisher_native_lavori_lot():
    payload = _notice(
        lots=[
            _lot("WORK-CIG", nature="Lavori"),
            _lot("SERVICE-CIG", nature="Servizi", cpv="Servizi di ingegneria"),
        ]
    )
    connector, _ = _single_day_connector([payload])
    rows, _ = connector.fetch_incremental(now=NOW)
    assert [row["external_id"] for row in rows] == ["WORK-CIG"]


def test_title_keywords_cannot_promote_nonworks_lot():
    payload = _notice(lots=[_lot("SERVICE-CIG", nature="Servizi", cpv="LAVORI STRADALI")])
    connector, _ = _single_day_connector([payload])
    rows, _ = connector.fetch_incremental(now=NOW)
    assert rows == []


def test_rectification_replaces_same_cig_and_updates_deadline_without_duplicate():
    original = _notice(notice_id="n1", published="2026-08-24T08:00:00Z")
    corrected = _notice(
        notice_id="n2",
        notice_type="rettifica",
        published="2026-08-24T10:00:00Z",
        created="2026-08-24T09:30:00Z",
        lots=[_lot(deadline="2026-10-13T12:00:00+02:00")],
        top_deadline="2026-10-13T10:00:00Z",
    )
    connector, _ = _single_day_connector([corrected, original])
    rows, _ = connector.fetch_incremental(now=NOW)

    assert len(rows) == 1
    assert rows[0]["external_id"] == "BCB6E8D60A"
    assert rows[0]["deadline"] == "2026-10-13T10:00:00Z"
    assert rows[0]["source_status"] == "rettifica"
    assert rows[0]["source_reference"] == "n2"
    assert rows[0]["published_at"] == "2026-08-24T08:00:00Z"
    assert rows[0]["source_updated_at"] == "2026-08-24T10:00:00Z"


def test_older_rectification_cannot_overwrite_newer_state():
    newer = _notice(notice_id="new", published="2026-08-24T11:00:00Z")
    older = _notice(
        notice_id="old",
        notice_type="rettifica",
        published="2026-08-24T09:00:00Z",
        lots=[_lot(deadline="2026-08-25T12:00:00+02:00")],
    )
    connector, _ = _single_day_connector([newer, older])
    rows, _ = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["source_reference"] == "new"
    assert rows[0]["deadline"] == "2026-09-16T13:00:00Z"


def test_newer_version_that_changes_lot_to_nonworks_emits_lifecycle_tombstone():
    first_connector, _ = _single_day_connector([_notice()])
    first_rows, watermark = first_connector.fetch_incremental(now=NOW)
    assert first_rows[0]["is_actionable"] is True

    changed = _notice(
        notice_id="notice-2",
        notice_type="rettifica",
        published="2026-08-25T08:00:00Z",
        created="2026-08-25T07:00:00Z",
        lots=[_lot(nature="Servizi")],
    )
    session = _Session({("24/08/2026", 0): _page([_notice()]), ("25/08/2026", 0): _page([changed])})
    connector = ANACPVLConnector(session=session, overlap_days=1, max_days_per_sync=2)
    rows, _ = connector.fetch_incremental(watermark=watermark, now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc))

    assert len(rows) == 1
    assert rows[0]["external_id"] == "BCB6E8D60A"
    assert rows[0]["is_actionable"] is False
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "not_construction"


def test_newer_inactive_works_version_closes_previously_visible_lot():
    first_connector, _ = _single_day_connector([_notice()])
    _, watermark = first_connector.fetch_incremental(now=NOW)

    inactive = _notice(
        notice_id="notice-2",
        notice_type="rettifica",
        published="2026-08-25T08:00:00Z",
        created="2026-08-25T07:00:00Z",
        active=False,
    )
    session = _Session({("24/08/2026", 0): _page([_notice()]), ("25/08/2026", 0): _page([inactive])})
    connector = ANACPVLConnector(session=session, overlap_days=1, max_days_per_sync=2)
    rows, _ = connector.fetch_incremental(watermark=watermark, now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["lifecycle_status"] == "publisher_inactive"
    assert rows[0]["_lifecycle_only"] is True


def test_expired_deadline_is_not_exposed_as_actionable():
    payload = _notice(lots=[_lot(deadline="2026-08-24T10:00:00+00:00")], top_deadline="2026-08-24T10:00:00Z")
    connector, _ = _single_day_connector([payload])
    rows, cursor = connector.fetch_incremental(now=NOW)
    assert rows == []
    assert ANACPVLCursor.decode(cursor).tracked == {}


def test_date_only_lot_deadline_uses_precise_top_level_deadline():
    payload = _notice(lots=[_lot(deadline="2026-09-16+02:00")], top_deadline="2026-09-16T13:00:00Z")
    connector, _ = _single_day_connector([payload])
    rows, _ = connector.fetch_incremental(now=NOW)
    assert rows[0]["deadline"] == "2026-09-16T13:00:00Z"


def test_works_lot_missing_cig_fails_closed():
    payload = _notice(lots=[_lot(cig="")])
    connector, _ = _single_day_connector([payload])
    with pytest.raises(RuntimeError, match="missing CIG"):
        connector.fetch_incremental(now=NOW)


def test_works_notice_with_unknown_tipo_fails_closed():
    connector, _ = _single_day_connector([_notice(notice_type="esito")])
    with pytest.raises(RuntimeError, match="unsupported tipo"):
        connector.fetch_incremental(now=NOW)


def test_works_notice_missing_publisher_identity_fails_closed():
    connector, _ = _single_day_connector([_notice(notice_id="")])
    with pytest.raises(RuntimeError, match="missing idAvviso"):
        connector.fetch_incremental(now=NOW)


def test_duplicate_notice_across_pages_fails_closed():
    row = _notice()
    session = _Session(
        {
            ("24/08/2026", 0): _page([row], page=0, total_pages=2, total_elements=2),
            ("24/08/2026", 1): _page([row], page=1, total_pages=2, total_elements=2),
        }
    )
    connector = ANACPVLConnector(session=session, initial_lookback_days=1, overlap_days=0, max_days_per_sync=1)
    with pytest.raises(RuntimeError, match="duplicate idAvviso"):
        connector.fetch_incremental(now=NOW)


def test_pagination_count_mismatch_fails_closed():
    session = _Session({("24/08/2026", 0): _page([_notice()], total_elements=2)})
    connector = ANACPVLConnector(session=session, initial_lookback_days=1, overlap_days=0, max_days_per_sync=1)
    with pytest.raises(RuntimeError, match="count mismatch"):
        connector.fetch_incremental(now=NOW)


def test_daily_hard_page_limit_fails_before_cursor_advance():
    session = _Session({("24/08/2026", 0): _page([], total_pages=81, total_elements=1)})
    connector = ANACPVLConnector(
        session=session,
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
        max_pages_per_day=80,
    )
    with pytest.raises(RuntimeError, match="hard limits"):
        connector.fetch_incremental(now=NOW)


def test_corrupt_and_future_cursor_are_rejected():
    connector, _ = _single_day_connector([])
    with pytest.raises(RuntimeError, match="cursor JSON"):
        connector.fetch_incremental(watermark="not-json", now=NOW)

    future = ANACPVLCursor("2026-08-25", {}, {}).encode()
    with pytest.raises(RuntimeError, match="ahead"):
        connector.fetch_incremental(watermark=future, now=NOW)


def test_partial_catchup_does_not_publish_intermediate_truth():
    session = _Session(
        {
            ("22/08/2026", 0): _page([_notice(published="2026-08-22T08:00:00Z")]),
        }
    )
    connector = ANACPVLConnector(
        session=session,
        initial_lookback_days=3,
        overlap_days=0,
        max_days_per_sync=1,
    )
    rows, cursor = connector.fetch_incremental(now=NOW)
    decoded = ANACPVLCursor.decode(cursor)
    assert rows == []
    assert decoded.completed_through == "2026-08-22"
    assert "BCB6E8D60A" in decoded.tracked


def test_same_day_overlap_is_requeried_so_later_rectification_is_seen():
    original = _notice(notice_id="n1", published="2026-08-24T08:00:00Z")
    first_connector, first_session = _single_day_connector([original])
    first_rows, watermark = first_connector.fetch_incremental(now=NOW)
    assert first_rows[0]["source_reference"] == "n1"
    assert len(first_session.calls) == 1

    corrected = _notice(
        notice_id="n2",
        notice_type="rettifica",
        published="2026-08-24T15:00:00Z",
        created="2026-08-24T14:59:00Z",
        lots=[_lot(deadline="2026-10-01T12:00:00+02:00")],
        top_deadline="2026-10-01T10:00:00Z",
    )
    session = _Session({("24/08/2026", 0): _page([original, corrected], total_elements=2)})
    connector = ANACPVLConnector(session=session, overlap_days=1, max_days_per_sync=2)
    rows, _ = connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 24, 18, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["source_reference"] == "n2"
    assert rows[0]["deadline"] == "2026-10-01T10:00:00Z"


def test_fetch_uses_bounded_official_day_window_and_no_credentials():
    connector, session = _single_day_connector([])
    connector.fetch_incremental(now=NOW)
    _, params, headers, timeout = session.calls[0]
    assert params["dataPubblicazioneStart"] == "24/08/2026"
    assert params["dataPubblicazioneEnd"] == "24/08/2026"
    assert params["sortField"] == "dataPubblicazione"
    assert params["sortDirection"] == "ASC"
    assert params["ricercaArchivio"] == "true"
    assert params["size"] == 100
    assert "Authorization" not in headers
    assert timeout == 60
