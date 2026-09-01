from datetime import datetime, timezone
import os

import pytest

from chile_mercadopublico import (
    MercadoPublicoConnector,
    MercadoPublicoCredentialError,
    MercadoPublicoCursor,
    TEST_TICKET,
    _is_construction,
    _observation,
)


class FakeResponse:
    def __init__(self, payload, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return self.responses.pop(0)


def tender(**overrides):
    base = {
        "CodigoExterno": "1000-1-LE26",
        "Nombre": "Conservación de edificio público",
        "CodigoEstado": 5,
        "Estado": "Publicada",
        "Descripcion": "Mantención y reparación",
        "Comprador": {
            "CodigoOrganismo": "123",
            "NombreOrganismo": "Municipalidad",
            "CodigoUnidad": "456",
            "NombreUnidad": "Obras",
            "ComunaUnidad": "Santiago",
            "RegionUnidad": "Región Metropolitana",
        },
        "Tipo": "LE",
        "Moneda": "CLP",
        "Obras": "0",
        "VisibilidadMonto": 1,
        "MontoEstimado": 50000000,
        "SubContratacion": "1",
        "Fechas": {
            "FechaPublicacion": "2026-08-24T10:00:00",
            "FechaCierre": "2099-09-01T15:00:00",
        },
        "Items": {"Cantidad": 1, "Listado": [{
            "CodigoCategoria": "72131700",
            "NombreProducto": "Construcción de obras civiles",
            "Descripcion": "Obra de mantención",
        }]},
    }
    base.update(overrides)
    return base


def api(rows):
    return {"Cantidad": len(rows), "FechaCreacion": "2026-08-25T00:00:00Z", "Version": "v1", "Listado": rows}


def test_requires_real_ticket_and_rejects_documentation_ticket_by_default(monkeypatch):
    monkeypatch.delenv("MERCADOPUBLICO_TICKET", raising=False)
    with pytest.raises(MercadoPublicoCredentialError, match="required"):
        MercadoPublicoConnector()
    with pytest.raises(MercadoPublicoCredentialError, match="test-only"):
        MercadoPublicoConnector(ticket=TEST_TICKET)


def test_explicit_works_flag_or_unspsc_72_admits_construction_without_keywords():
    assert _is_construction(tender(Obras="2", Items={"Cantidad": 0, "Listado": []})) is True
    assert _is_construction(tender(Obras="0")) is True
    assert _is_construction(tender(
        Nombre="Vigas para puente",
        Descripcion="material para obra",
        Obras="0",
        Items={"Cantidad": 1, "Listado": [{"CodigoCategoria": "30101700", "NombreProducto": "Vigas de acero"}]},
    )) is False


def test_observation_uses_visible_amount_only_and_preserves_publisher_state():
    item = _observation(tender())
    assert item["external_id"] == "1000-1-LE26"
    assert item["taxonomy"] == "UNSPSC"
    assert item["unspsc_codes"] == ["72131700"]
    assert item["value"] == "50000000"
    assert item["currency"] == "CLP"
    assert item["lifecycle_status"] == "open"
    assert item["is_actionable"] is True
    hidden = _observation(tender(VisibilidadMonto=0, MontoEstimado=999999999))
    assert hidden["value"] == ""
    assert hidden["currency"] == ""


def test_rate_limit_retries_sequentially_without_advancing_cursor(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ALLOW_MERCADOPUBLICO_TEST_TICKET", "1")
    sleeps = []
    session = FakeSession([
        FakeResponse({}, status=429, text='{"Codigo":10500}'),
        FakeResponse(api([])),
    ])
    conn = MercadoPublicoConnector(ticket=TEST_TICKET, session=session, sleeper=sleeps.append, min_interval_seconds=0)
    out = conn._get({"fecha": "24082026"})
    assert out["Cantidad"] == 0
    assert len(session.calls) == 2
    assert sleeps == [5.0]


def test_incremental_fetch_discovers_only_new_candidates_and_resolves_disappearance(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ALLOW_MERCADOPUBLICO_TEST_TICKET", "1")
    # day-1 list, current-day list, active list, new detail, disappeared detail
    closed = tender(CodigoExterno="old-work", CodigoEstado=6, Estado="Cerrada")
    session = FakeSession([
        FakeResponse(api([{"CodigoExterno": "already-seen"}, {"CodigoExterno": "new-work"}])),
        FakeResponse(api([])),
        FakeResponse(api([{"CodigoExterno": "new-work"}])),
        FakeResponse(api([tender(CodigoExterno="new-work")])),
        FakeResponse(api([closed])),
    ])
    now = lambda: datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    watermark = MercadoPublicoCursor(
        seen_by_day={"2026-08-24": ["already-seen"]},
        tracked=["old-work"],
    ).encode()
    conn = MercadoPublicoConnector(ticket=TEST_TICKET, session=session, sleeper=lambda _: None, min_interval_seconds=0, now_fn=now)
    rows, cursor = conn.fetch(watermark=watermark)
    assert [(r["external_id"], r["lifecycle_status"]) for r in rows] == [
        ("new-work", "open"),
        ("old-work", "closed"),
    ]
    decoded = MercadoPublicoCursor.decode(cursor)
    assert decoded.tracked == ["new-work"]
    assert decoded.seen_by_day["2026-08-24"] == ["already-seen", "new-work"]


def test_nonconstruction_detail_is_seen_but_never_emitted_or_tracked(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ALLOW_MERCADOPUBLICO_TEST_TICKET", "1")
    nonwork = tender(
        CodigoExterno="goods-1",
        Obras="0",
        Items={"Cantidad": 1, "Listado": [{"CodigoCategoria": "30101700", "NombreProducto": "Vigas"}]},
    )
    session = FakeSession([
        FakeResponse(api([{"CodigoExterno": "goods-1"}])),
        FakeResponse(api([])),
        FakeResponse(api([{"CodigoExterno": "goods-1"}])),
        FakeResponse(api([nonwork])),
    ])
    conn = MercadoPublicoConnector(
        ticket=TEST_TICKET,
        session=session,
        sleeper=lambda _: None,
        min_interval_seconds=0,
        now_fn=lambda: datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
    )
    rows, cursor = conn.fetch()
    assert rows == []
    assert MercadoPublicoCursor.decode(cursor).tracked == []
