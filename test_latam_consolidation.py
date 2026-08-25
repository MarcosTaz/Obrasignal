"""Cross-cell guards for the LATAM consolidation branch.

These tests intentionally verify integration boundaries rather than live source
availability. Production promotion remains a separate, explicit operation.
"""
from datetime import date
from pathlib import Path

from dominican_republic_dgcp import normalize_dgcp_signals
from dominican_republic_dgcp_pacc import normalize_dgcp_pacc_acquisition
from shared_source_families import FAMILIES, family_for_source
from source_registry import SOURCES
from uruguay_arce_pac import normalize_arce_pac_procedure


def test_dominican_republic_is_one_planned_source_in_shared_ocds_family():
    source = SOURCES["DO_DGCP"]
    assert source["country"] == "DOM"
    assert source["source_id"] == "do_dgcp_open_data"
    assert source["status"] == "planned"
    assert source["machine_access"] == "VERIFIED"
    assert source["capabilities"] == (
        "incremental_sync", "detail", "plans", "awards", "contracts", "lifecycle"
    )
    assert source["signal_types"] == (
        "PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"
    )
    assert family_for_source("DO_DGCP") is FAMILIES["OCDS_PAGE_API"]
    assert FAMILIES["OCDS_PAGE_API"].members.count("DO_DGCP") == 1


def test_uruguay_pac_deepens_existing_ready_source_without_duplicate_identity():
    assert "UY_ARCE" in SOURCES
    assert "UY_ARCE_PAC" not in SOURCES
    source = SOURCES["UY_ARCE"]
    assert source["source_id"] == "uy_arce_ocds"
    assert source["status"] == "ready"
    assert "plans" in source["capabilities"]
    assert source["signal_types"] == ("PROCUREMENT_PLAN", "TENDER")
    assert source["adapter"] == "ARCEOCDSRSSAdapter+ARCEPACConnector"


def test_uruguay_preload_stages_all_signals_but_returns_only_legacy_tenders():
    text = Path("preload.py").read_text(encoding="utf-8")
    assert "import uruguay_arce_runtime as _uruguay_arce_runtime" in text
    assert "batch = _uruguay_arce_runtime.fetch_arce_runtime_batch(watermark=watermark)" in text
    assert 'stage_source_sync("UY_ARCE", batch.signals, batch.cursor)' in text
    assert "return list(batch.legacy_tenders)" in text


def test_uruguay_pac_signal_keeps_canonical_source_identity():
    row = {
        "id": 7,
        "objetoCompra": "Objeto controlado por familia de construcción",
        "periodoConvFechaIni": "2026-09-10",
        "periodoConvFechaFin": "2026-09-20",
        "dadoBaja": False,
        "planAnual": {"id": 2, "descUnidadCompra": "Unidad", "anioPlan": 2026},
    }
    item = normalize_arce_pac_procedure(row, today=date(2026, 8, 25))
    assert item is not None
    assert item["source"] == "UY_ARCE"
    assert item["signal_type"] == "PROCUREMENT_PLAN"
    assert item["external_id"] == "pac:7"
    assert item["category_code"] == "6"


def test_dgcp_pacc_and_lifecycle_share_one_source_identity():
    plan = normalize_dgcp_pacc_acquisition({
        "id_adquisicion": "A1",
        "uid_pacc": "P1",
        "unidad_compra": "Unidad",
        "objeto_adquisicion": "Obras",
        "fecha_inicio_proceso_compra": "2026-10-01",
        "descripcion": "Construcción",
        "valor_presupuestado": "1000",
    })
    assert plan is not None
    assert plan["source"] == "DO_DGCP"
    assert plan["signal_type"] == "PROCUREMENT_PLAN"

    record = {
        "ocid": "ocds-test-1",
        "releases": [{
            "ocid": "ocds-test-1",
            "date": "2026-08-01T10:00:00Z",
            "buyer": {"name": "Buyer"},
            "tender": {
                "id": "T1",
                "title": "Works tender",
                "mainProcurementCategory": "works",
                "status": "active",
            },
            "awards": [{"id": "A1", "status": "active"}],
            "contracts": [{"id": "C1", "awardID": "A1", "status": "active"}],
        }],
    }
    signals = normalize_dgcp_signals(record)
    assert {item["signal_type"] for item in signals} == {"TENDER", "AWARD", "CONTRACT"}
    assert {item["source"] for item in signals} == {"DO_DGCP"}
