from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from dominican_republic_dgcp import DGCP_CONFIG, DGCP_OCDS_DETAIL_URL_TEMPLATE
from dominican_republic_dgcp_discovery import (
    DGCP_PROCESSES_URL,
    DGCPProcessDiscoveryConnector,
    dgcp_process_search_params,
    fetch_dgcp_signals_complete,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        if not self.responses:
            raise AssertionError("unexpected request")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return FakeResponse(value)


def _process(code, *, obj="Obras", published="2026-08-25T12:00:00Z", subobj="Obras no complejas"):
    return {
        "codigo_proceso": code,
        "objeto_proceso": obj,
        "subobjeto_proceso": subobj,
        "fecha_publicacion": published,
        "estado_proceso": "Proceso publicado",
        "titulo": f"Proceso {code}",
    }


def _page(rows, *, page=1, pages=1, limit=2, total=None):
    return {
        "code": 200,
        "hasError": False,
        "page": page,
        "pages": pages,
        "limit": limit,
        "totalResults": len(rows) if total is None else total,
        "payload": {"content": list(rows)},
    }


def _detail(code, *, category="works", status="active"):
    ocid = f"ocds-6550wx-{code}"
    return {
        "version": "1.1",
        "releases": [{
            "ocid": ocid,
            "id": f"{ocid}-release",
            "date": "2026-08-25T13:00:00-04:00",
            "tag": ["tender"],
            "buyer": {"name": "Unidad de Compra"},
            "tender": {
                "id": f"{ocid}-tender",
                "title": f"Obra {code}",
                "description": "Construcción",
                "status": status,
                "mainProcurementCategory": category,
                "tenderPeriod": {"endDate": "2026-09-20T10:00:00-04:00"},
                "items": [{"classification": {"scheme": "UNSPSC", "id": "72131600"}}],
            },
        }],
    }


def _config(**changes):
    base = dict(
        page_size=2,
        max_pages_per_window=3,
        initial_lookback_days=0,
        overlap_days=0,
        max_windows_per_sync=1,
        max_hydrations_per_window=10,
    )
    base.update(changes)
    return replace(DGCP_CONFIG, **base)


def test_process_search_params_use_documented_publication_window_names():
    assert dgcp_process_search_params(date(2026, 8, 24), date(2026, 8, 25)) == {
        "startdate": "2026-08-24",
        "enddate": "2026-08-25",
    }


def test_complete_discovery_paginates_all_processes_then_hydrates_only_publisher_obras():
    config = _config()
    session = FakeSession([
        _page([_process("A"), _process("B", obj="Servicios")], page=1, pages=2, limit=2, total=3),
        _page([_process("C")], page=2, pages=2, limit=2, total=3),
        _detail("A"),
        _detail("C"),
    ])
    connector = DGCPProcessDiscoveryConnector(config, session=session)
    rows, cursor = fetch_dgcp_signals_complete(
        connector=connector,
        now=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    assert [row["external_id"] for row in rows] == ["ocds-6550wx-A", "ocds-6550wx-C"]
    assert all(row["signal_type"] == "TENDER" for row in rows)
    assert cursor == '{"completed_through":"2026-08-25"}'
    assert [call["url"] for call in session.calls] == [
        DGCP_PROCESSES_URL,
        DGCP_PROCESSES_URL,
        DGCP_OCDS_DETAIL_URL_TEMPLATE.format(ocid="ocds-6550wx-A"),
        DGCP_OCDS_DETAIL_URL_TEMPLATE.format(ocid="ocds-6550wx-C"),
    ]
    assert session.calls[0]["params"] == {
        "startdate": "2026-08-25",
        "enddate": "2026-08-25",
        "page": "1",
        "limit": "2",
    }
    assert session.calls[1]["params"]["page"] == "2"


def test_process_pagination_total_must_be_stable_and_complete_before_hydration():
    session = FakeSession([
        _page([_process("A"), _process("B", obj="Servicios")], page=1, pages=2, limit=2, total=3),
        _page([_process("C")], page=2, pages=2, limit=2, total=4),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(), session=session)
    with pytest.raises(RuntimeError, match="metadata changed"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))
    assert len(session.calls) == 2


def test_declared_total_mismatch_fails_closed_before_cursor_or_hydration():
    session = FakeSession([
        _page([_process("A")], page=1, pages=1, limit=2, total=2),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(), session=session)
    with pytest.raises(RuntimeError, match="fetched 1 rows.*declared totalResults=2"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))
    assert len(session.calls) == 1


def test_duplicate_process_identity_fails_instead_of_silent_dedupe():
    session = FakeSession([
        _page([_process("A"), _process("A")], page=1, pages=1, limit=2, total=2),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(), session=session)
    with pytest.raises(RuntimeError, match="duplicate process identity"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))


def test_process_outside_requested_publication_window_fails_closed():
    session = FakeSession([
        _page([_process("A", published="2026-08-24T23:59:59Z")], page=1, pages=1, limit=2, total=1),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(), session=session)
    with pytest.raises(RuntimeError, match="falls outside"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))


def test_window_above_page_bound_fails_before_fetching_every_page():
    session = FakeSession([
        _page([_process("A")], page=1, pages=4, limit=2, total=7),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(max_pages_per_window=3), session=session)
    with pytest.raises(RuntimeError, match="above max_pages_per_window"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))
    assert len(session.calls) == 1


def test_works_candidate_above_hydration_bound_fails_before_any_detail_request():
    session = FakeSession([
        _page([_process("A"), _process("B")], page=1, pages=1, limit=2, total=2),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(max_hydrations_per_window=1), session=session)
    with pytest.raises(RuntimeError, match="above max_hydrations_per_window"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))
    assert len(session.calls) == 1


def test_publisher_obras_vs_ocds_nonworks_mismatch_fails_instead_of_false_negative():
    session = FakeSession([
        _page([_process("A")], page=1, pages=1, limit=2, total=1),
        _detail("A", category="services"),
    ])
    connector = DGCPProcessDiscoveryConnector(_config(), session=session)
    with pytest.raises(RuntimeError, match="publisher process A is Obras.*not mainProcurementCategory=works"):
        connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25))


def test_non_obras_never_hydrates_even_when_title_contains_construction_words():
    process = _process("A", obj="Servicios")
    process["titulo"] = "Construcción mantenimiento obra civil"
    session = FakeSession([_page([process], page=1, pages=1, limit=2, total=1)])
    connector = DGCPProcessDiscoveryConnector(_config(), session=session)
    assert connector._fetch_window(date(2026, 8, 25), date(2026, 8, 25)) == []
    assert len(session.calls) == 1
