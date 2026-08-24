from datetime import datetime, timedelta

import pytest
import requests

import brazil_pncp_pca as br


def _search(id_, update, cnpj="11111111000111", year="2026"):
    return {
        "id": id_,
        "orgao_cnpj": cnpj,
        "ano": year,
        "data_atualizacao_pncp": update,
        "data_publicacao_pncp": "2026-01-01T00:00:00",
        "orgao_nome": "Comprador",
        "item_url": f"/pca/{cnpj}/{year}",
    }


def test_recent_scan_rejects_publisher_order_reversal(monkeypatch):
    monkeypatch.setattr(br, "SEARCH_PAGE_SIZE", 3)
    monkeypatch.setattr(
        br,
        "_search_page",
        lambda page: ([
            _search("a", "2026-08-24T18:00:00"),
            _search("b", "2026-08-24T18:01:00"),
            _search("c", "2026-08-24T17:00:00"),
        ], 3),
    )
    with pytest.raises(RuntimeError, match="not recent-first"):
        br._scan_recent_once(datetime(2026, 8, 24, 16, 0, 0))


def test_recent_scan_rejects_duplicate_ids_across_pages(monkeypatch):
    monkeypatch.setattr(br, "SEARCH_PAGE_SIZE", 2)
    monkeypatch.setattr(br, "SEARCH_MAX_PAGES", 3)
    pages = {
        1: ([_search("a", "2026-08-24T18:00:00"), _search("b", "2026-08-24T17:50:00")], 4),
        2: ([_search("b", "2026-08-24T17:40:00"), _search("c", "2026-08-24T17:30:00")], 4),
    }
    monkeypatch.setattr(br, "_search_page", lambda page: pages[page])
    with pytest.raises(RuntimeError, match="duplicate national search id"):
        br._scan_recent_once(datetime(2026, 8, 24, 17, 0, 0))


def test_recent_scan_fails_if_page_bound_is_reached_before_cutoff(monkeypatch):
    monkeypatch.setattr(br, "SEARCH_PAGE_SIZE", 1)
    monkeypatch.setattr(br, "SEARCH_MAX_PAGES", 2)
    pages = {
        1: ([_search("a", "2026-08-24T18:00:00")], 100),
        2: ([_search("b", "2026-08-24T17:59:00")], 100),
    }
    monkeypatch.setattr(br, "_search_page", lambda page: pages[page])
    with pytest.raises(RuntimeError, match="backlog exceeds bounded"):
        br._scan_recent_once(datetime(2026, 8, 24, 1, 0, 0))


def test_stable_snapshot_rejects_drift_between_scans(monkeypatch):
    monkeypatch.setattr(
        br,
        "_search_page",
        lambda page: ([_search("top", "2026-08-24T18:00:00")], 1),
    )
    snapshots = [
        [{"id": "a", "cnpj": "1", "year": "2026", "updated": datetime(2026,8,24,18), "updated_raw": "", "published_raw": "", "buyer": "", "value_global": None, "cancelled": False, "item_url": ""}],
        [{"id": "b", "cnpj": "1", "year": "2026", "updated": datetime(2026,8,24,18), "updated_raw": "", "published_raw": "", "buyer": "", "value_global": None, "cancelled": False, "item_url": ""}],
    ]
    monkeypatch.setattr(br, "_scan_recent_once", lambda cutoff: snapshots.pop(0))
    with pytest.raises(RuntimeError, match="drifted between stable scans"):
        br._stable_recent_snapshot("2026-08-24T17:30:00")


def test_future_cursor_fails_closed(monkeypatch):
    monkeypatch.setattr(
        br,
        "_search_page",
        lambda page: ([_search("top", "2026-08-24T18:00:00")], 1),
    )
    with pytest.raises(RuntimeError, match="ahead of publisher"):
        br._stable_recent_snapshot("2026-08-25T18:00:00")


def test_fetch_hydrates_only_units_updated_inside_overlap_window(monkeypatch):
    search_row = {
        "id": "s1", "cnpj": "11111111000111", "year": "2026",
        "updated": datetime(2026,8,24,18), "updated_raw": "2026-08-24T18:00:00",
        "published_raw": "", "buyer": "Buyer", "value_global": None,
        "cancelled": False, "item_url": "/pca/11111111000111/2026",
    }
    cutoff = datetime(2026,8,24,17,30)
    monkeypatch.setattr(br, "_stable_recent_snapshot", lambda watermark: ([search_row], datetime(2026,8,24,18), cutoff))
    units = [
        {"cnpj":"11111111000111","anoPca":2026,"sequencialPca":1,"numeroControlePNCP":"11111111000111-0-000001/2026","dataAtualizacao":"2026-08-24T17:50:00","dataPublicacaoPncp":"2026-01-01","razaoSocial":"Buyer","_updated":datetime(2026,8,24,17,50)},
        {"cnpj":"11111111000111","anoPca":2026,"sequencialPca":2,"numeroControlePNCP":"11111111000111-0-000002/2026","dataAtualizacao":"2026-08-24T10:00:00","dataPublicacaoPncp":"2026-01-01","razaoSocial":"Buyer","_updated":datetime(2026,8,24,10)},
    ]
    monkeypatch.setattr(br, "_consolidated_units", lambda cnpj, year: units)
    calls=[]

    def items(cnpj, year, seq, category):
        calls.append((seq, category))
        if seq != "1" or category != "8":
            return []
        return [{
            "cnpj":"11111111000111","anoPca":2026,"sequencialPca":1,"numeroItem":9,
            "categoriaItemPcaid":8,"categoriaItemPcaNome":"Obras e Serviços de Engenharia",
            "descricao":"Obra pública","valorTotal":100,"dataDesejada":"2026-11-01",
            "dataAtualizacao":"2026-08-24T17:45:00","dataPublicacaoPncp":"2026-01-01",
        }]
    monkeypatch.setattr(br, "_category_items", items)

    signals, cursor = br.fetch_brazil_pncp_pca_plans(watermark="2026-08-24T18:00:00")
    assert cursor == "2026-08-24T18:00:00.000000"
    assert len(signals) == 1
    assert signals[0]["external_id"] == "11111111000111-0-000001/2026:9"
    assert {seq for seq, _ in calls} == {"1"}
    assert {category for _, category in calls} == {"3", "4", "8"}


def test_request_json_retries_transient_transport_failure_with_fresh_calls(monkeypatch):
    class Response:
        status_code = 200
        content = b"{}"
        def raise_for_status(self):
            return None
        def json(self):
            return {"ok": True}

    attempts = []
    def fake_get(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise requests.ConnectionError("closed")
        return Response()

    monkeypatch.setattr(br.requests, "get", fake_get)
    monkeypatch.setattr(br.time, "sleep", lambda seconds: None)
    assert br._request_json("https://example.invalid") == {"ok": True}
    assert len(attempts) == 2


def test_invalid_cursor_never_falls_back_silently(monkeypatch):
    monkeypatch.setattr(
        br,
        "_search_page",
        lambda page: ([_search("top", "2026-08-24T18:00:00")], 1),
    )
    with pytest.raises(RuntimeError, match="invalid cursor"):
        br._stable_recent_snapshot("not-a-timestamp")
