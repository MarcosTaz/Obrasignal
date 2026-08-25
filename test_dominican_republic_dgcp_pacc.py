from datetime import datetime, timezone
from dataclasses import replace

import pytest

from dominican_republic_dgcp_pacc import (
    DGCPPACCConfig,
    DGCPPACCConnector,
    DGCP_PACC_ACQUISITIONS_URL,
    normalize_dgcp_pacc_acquisition,
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
        self.calls.append((url, dict(params), dict(headers), timeout))
        if not self.responses:
            raise AssertionError("unexpected request")
        return FakeResponse(self.responses.pop(0))


def envelope(rows, *, code=200, has_error=False):
    return {"code": code, "hasError": has_error, "payload": {"content": rows}}


def acquisition(**overrides):
    row = {
        "codigo_unidad_compra": 10001,
        "descripcion": "Construcción y rehabilitación de vía pública",
        "dirigido_mipymes": False,
        "dirigido_mipymes_mujeres": False,
        "fecha_inicio_proceso_compra": "2026-10-15T00:00:00",
        "finalidad": "Mejorar infraestructura vial",
        "id_adquisicion": "ADQ-42",
        "modalidad_adquisicion": "Licitación Pública Nacional",
        "objeto_adquisicion": "Obras",
        "uid_pacc": "PACC-2026-UC-10001",
        "unidad_compra": "Ministerio de Obras Públicas",
        "valor_presupuestado": "125000000.50",
        "version": 3,
    }
    row.update(overrides)
    return row


def test_normalizes_only_publisher_controlled_works_object():
    item = normalize_dgcp_pacc_acquisition(acquisition())
    assert item["source"] == "DO_DGCP"
    assert item["signal_type"] == "PROCUREMENT_PLAN"
    assert item["external_id"] == "PACC-2026-UC-10001:ADQ-42"
    assert item["buyer"] == "Ministerio de Obras Públicas"
    assert item["country"] == "DOM"
    assert item["value"] == "125000000.50"
    assert item["currency"] == "DOP"
    assert item["target_date"] == "2026-10-15"
    assert item["taxonomy"] == "DGCP_PACC_OBJECT"
    assert item["category_code"] == "OBRAS"
    assert item["contract_type"] == "works"
    assert item["pacc_version"] == 3

    assert normalize_dgcp_pacc_acquisition(acquisition(objeto_adquisicion="Bienes")) is None
    assert normalize_dgcp_pacc_acquisition(acquisition(objeto_adquisicion="Servicios")) is None
    assert normalize_dgcp_pacc_acquisition(acquisition(objeto_adquisicion="ÓBRAS")) is not None


def test_rejects_weak_identity_or_invalid_target_date():
    assert normalize_dgcp_pacc_acquisition(acquisition(id_adquisicion="")) is None
    assert normalize_dgcp_pacc_acquisition(acquisition(uid_pacc="")) is None
    assert normalize_dgcp_pacc_acquisition(acquisition(unidad_compra="")) is None
    assert normalize_dgcp_pacc_acquisition(acquisition(fecha_inicio_proceso_compra="not-a-date")) is None


def test_invalid_or_negative_value_does_not_poison_signal():
    invalid = normalize_dgcp_pacc_acquisition(acquisition(valor_presupuestado="n/a"))
    assert invalid["value"] == ""
    assert invalid["currency"] == ""
    negative = normalize_dgcp_pacc_acquisition(acquisition(valor_presupuestado="-1"))
    assert negative["value"] == ""


def test_snapshot_paginates_filters_latest_versions_and_expired_plans():
    config = replace(DGCPPACCConfig(), page_size=2, max_pages=4)
    first = acquisition(version=2, descripcion="old version")
    goods = acquisition(id_adquisicion="GOODS", objeto_adquisicion="Bienes")
    latest = acquisition(version=4, descripcion="latest version")
    second = acquisition(id_adquisicion="ADQ-43")
    expired = acquisition(id_adquisicion="OLD", fecha_inicio_proceso_compra="2026-08-24")
    session = FakeSession([
        envelope([first, goods]),
        envelope([latest, second]),
        envelope([expired]),
    ])
    connector = DGCPPACCConnector(config, session=session)
    rows = connector.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))

    assert [row["external_id"] for row in rows] == [
        "PACC-2026-UC-10001:ADQ-42",
        "PACC-2026-UC-10001:ADQ-43",
    ]
    assert rows[0]["pacc_version"] == 4
    assert rows[0]["title"] == "latest version"
    assert [call[1]["page"] for call in session.calls] == [1, 2, 3]
    assert all(call[0] == DGCP_PACC_ACQUISITIONS_URL for call in session.calls)
    assert all(call[1]["año"] == 2026 for call in session.calls)


def test_plan_targeted_today_remains_actionable():
    session = FakeSession([envelope([acquisition(fecha_inicio_proceso_compra="2026-08-25")])])
    connector = DGCPPACCConnector(replace(DGCPPACCConfig(), page_size=10), session=session)
    rows = connector.fetch_snapshot(now=datetime(2026, 8, 25, tzinfo=timezone.utc))
    assert len(rows) == 1


def test_snapshot_fails_closed_when_page_bound_cannot_prove_completeness():
    config = replace(DGCPPACCConfig(), page_size=1, max_pages=2)
    session = FakeSession([envelope([acquisition()]), envelope([acquisition(id_adquisicion="ADQ-43")])])
    connector = DGCPPACCConnector(config, session=session)
    with pytest.raises(RuntimeError, match="snapshot completeness not proven"):
        connector.fetch_snapshot(year=2026, now=datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_snapshot_fails_closed_on_bad_envelope_or_content_shape():
    connector = DGCPPACCConnector(replace(DGCPPACCConfig(), page_size=10), session=FakeSession([
        {"code": 500, "hasError": True, "payload": {"content": []}},
    ]))
    with pytest.raises(RuntimeError, match="invalid API envelope"):
        connector.fetch_snapshot(year=2026, now=datetime(2026, 8, 25, tzinfo=timezone.utc))

    connector = DGCPPACCConnector(replace(DGCPPACCConfig(), page_size=10), session=FakeSession([
        {"code": 200, "hasError": False, "payload": {"content": "wrong"}},
    ]))
    with pytest.raises(RuntimeError, match="no content list"):
        connector.fetch_snapshot(year=2026, now=datetime(2026, 8, 25, tzinfo=timezone.utc))
