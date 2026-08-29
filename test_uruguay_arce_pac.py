from datetime import datetime, timezone

import pytest

from uruguay_arce_pac import (
    ARCE_PAC_CONFIG_URL,
    ARCE_PAC_PUBLIC_URL,
    ARCE_PAC_SEARCH_PATH,
    ARCEPACConfig,
    ARCEPACConnector,
    normalize_arce_pac_procedure,
)


class FakeResponse:
    def __init__(self, payload=None, *, status=200):
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

    def get(self, url, *, params=None, headers, timeout):
        self.calls.append({
            "url": url,
            "params": dict(params or {}),
            "headers": dict(headers),
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError(f"unexpected request {url}")
        return self.responses.pop(0)


def _row(
    *,
    procedure_id=101,
    plan_id=77,
    title="Objeto sem palavras-chave de construção",
    start="2026-09-10",
    end="2026-09-20",
    removed=False,
):
    return {
        "id": procedure_id,
        "objetoCompra": title,
        "periodoConvFechaIni": start,
        "periodoConvFechaFin": end,
        "fechaHoraPublicacion": "2026-08-01T10:00:00",
        "fechaHoraUltimaActualizacion": "2026-08-20T12:30:00",
        "dadoBaja": removed,
        "codTipoCompra": 2,
        "descTipoCompra": "Licitación",
        "codSubtipoCompra": 1,
        "descSubtipoCompra": "Abreviada",
        "planAnual": {
            "id": plan_id,
            "anioPlan": 2026,
            "codInciso": 10,
            "descInciso": "Inciso",
            "codUnidadCompra": 20,
            "descUnidadCompra": "Unidad de Compra",
            "codUnidadEjecutora": 30,
            "descUnidadEjecutora": "Unidad Ejecutora",
            "fechaPublicacion": "2026-07-01",
        },
    }


def _page(number, total_pages, rows):
    return {
        "content": rows,
        "number": number,
        "totalPages": total_pages,
        "totalElements": sum(1 for _ in rows),
    }


def _connector(responses, *, page_size=100, max_pages=50):
    return ARCEPACConnector(
        ARCEPACConfig(page_size=page_size, max_pages=max_pages),
        session=FakeSession(responses),
    )


def test_normalizer_emits_future_plan_without_keyword_admission_or_fake_value():
    item = normalize_arce_pac_procedure(_row(), today=datetime(2026, 8, 25).date())
    assert item is not None
    assert item["source"] == "UY_ARCE"
    assert item["signal_type"] == "PROCUREMENT_PLAN"
    assert item["external_id"] == "pac:101"
    assert item["taxonomy"] == "ARCE_PAC_FAMILY"
    assert item["category_code"] == "6"
    assert item["contract_type"] == "works"
    assert item["target_date"] == "2026-09-10"
    assert item["planned_window_end"] == "2026-09-20"
    assert item["buyer"] == "Unidad de Compra"
    assert item["value"] == ""
    assert item["currency"] == ""
    assert item["title"] == "Objeto sem palavras-chave de construção"


def test_normalizer_excludes_removed_started_malformed_and_inverted_windows():
    today = datetime(2026, 8, 25).date()
    assert normalize_arce_pac_procedure(_row(removed=True), today=today) is None
    assert normalize_arce_pac_procedure(_row(start="2026-08-24"), today=today) is None
    assert normalize_arce_pac_procedure(_row(start="bad"), today=today) is None
    assert normalize_arce_pac_procedure(_row(start="2026-09-10", end="2026-09-01"), today=today) is None
    broken = _row()
    broken["planAnual"] = {}
    assert normalize_arce_pac_procedure(broken, today=today) is None


def test_connector_bootstraps_same_origin_and_fetches_complete_bounded_snapshot():
    session = FakeSession([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse(_page(0, 2, [_row(procedure_id=1)])),
        FakeResponse(_page(1, 2, [_row(procedure_id=2)])),
    ])
    connector = ARCEPACConnector(ARCEPACConfig(page_size=100, max_pages=5), session=session)
    rows = connector.fetch_snapshot(now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc))

    assert [row["external_id"] for row in rows] == ["pac:1", "pac:2"]
    assert session.calls[0]["url"] == ARCE_PAC_PUBLIC_URL
    assert session.calls[0]["headers"]["Accept"].startswith("text/html")
    assert session.calls[1]["url"] == ARCE_PAC_CONFIG_URL
    search_calls = session.calls[2:]
    assert len(search_calls) == 2
    for index, call in enumerate(search_calls):
        assert call["url"].endswith(ARCE_PAC_SEARCH_PATH)
        assert call["params"]["page"] == index
        assert call["params"]["size"] == 100
        assert call["params"]["codFamilia"] == 6
        assert call["params"]["fechaConvocatoriaFinDesde"] == "2026-08-25"
        assert call["params"]["sort"] == "periodoConvFechaIni,asc"


def test_connector_fails_closed_on_config_origin_or_path_drift():
    for bad in ("https://evil.example/api", "/other", ""):
        connector = _connector([
            FakeResponse("html"),
            FakeResponse({"apiUrl": bad}),
        ])
        with pytest.raises(RuntimeError, match="apiUrl"):
            connector.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_connector_fails_closed_when_snapshot_exceeds_page_bound():
    connector = _connector([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse(_page(0, 51, [_row()])),
    ], max_pages=50)
    with pytest.raises(RuntimeError, match="above max_pages=50"):
        connector.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_connector_fails_closed_on_malformed_page_wrong_number_or_page_count_drift():
    malformed = _connector([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse({"content": "bad", "number": 0, "totalPages": 1}),
    ])
    with pytest.raises(RuntimeError, match="invalid paginated JSON"):
        malformed.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))

    wrong_number = _connector([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse(_page(1, 1, [_row()])),
    ])
    with pytest.raises(RuntimeError, match="page 1 while page 0"):
        wrong_number.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))

    drift = _connector([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse(_page(0, 2, [_row(procedure_id=1)])),
        FakeResponse(_page(1, 1, [_row(procedure_id=2)])),
    ])
    with pytest.raises(RuntimeError, match="totalPages changed"):
        drift.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_connector_fails_closed_on_empty_page_before_completion():
    connector = _connector([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse(_page(0, 2, [])),
    ])
    with pytest.raises(RuntimeError, match="empty page before snapshot completion"):
        connector.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_snapshot_deduplicates_by_stable_procedure_identity_and_keeps_latest_row():
    first = _row(procedure_id=9, title="Primeira versão")
    second = _row(procedure_id=9, title="Segunda versão")
    connector = _connector([
        FakeResponse("html"),
        FakeResponse({"apiUrl": "/consultaplananual"}),
        FakeResponse(_page(0, 1, [first, second])),
    ])
    rows = connector.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["external_id"] == "pac:9"
    assert rows[0]["title"] == "Segunda versão"
