from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database) -> tuple[IndustrialClaimsService, str]:
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="ECO-017",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="commercial basis",
        event_evidence_content="customer requested engineering change",
        cost_evidence_content="engineering cost record",
        notice_due=date(2026, 9, 30),
    )
    return service, result.finding.finding_id


def _schema_objects(database) -> list[tuple[str, str]]:
    with sqlite3.connect(database) as conn:
        return list(conn.execute(
            """SELECT type,name FROM sqlite_master
               WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"""
        ).fetchall())


def test_proof_pack_change_chronology_read_does_not_create_optional_proof_tables(tmp_path):
    database = tmp_path / "read-only-proof.sqlite3"
    service, finding = _case(database)
    capture = ChangeCaptureStore(database)
    capture.status(tenant_id="tenant-a", finding_id=finding)
    capture.add_fact(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-a",
        fact_type="REQUESTED_CHANGE",
        fact_text="Move mounting holes 8 mm.",
        source_ref="customer-email-1",
    )

    before = _schema_objects(database)
    before_names = {name for _kind, name in before}
    assert "causledger_change_sheet_attestations" not in before_names
    assert "causledger_change_late_supplements" not in before_names

    pack = build_durable_claim_proof_pack(
        service,
        tenant_id="tenant-a",
        finding_id=finding,
        generated_at="2026-09-01T00:00:00+00:00",
    )
    after = _schema_objects(database)

    assert after == before
    chronology = pack["core_package"]["change_chronology"]
    assert chronology["state"] == "CAPTURED"
    assert chronology["reader_side_effect_free"] is True
    assert chronology["current_snapshot_time_trust"]["persisted_attestation_state"] == "NO_PERSISTED_ATTESTATIONS"
    assert chronology["current_snapshot_time_trust"]["current_snapshot_externally_timestamped"] is False
    assert chronology["late_supplements"]["count"] == 0
    assert pack["core_package"]["truth_boundaries"]["proof_pack_generation_is_read_only"] is True


def test_proof_pack_fails_closed_on_partial_mandatory_capture_schema_without_repairing_it(tmp_path):
    database = tmp_path / "partial-proof.sqlite3"
    service, finding = _case(database)
    capture = ChangeCaptureStore(database)
    capture.status(tenant_id="tenant-a", finding_id=finding)

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TABLE causledger_change_facts")
    before = _schema_objects(database)
    assert "causledger_change_facts" not in {name for _kind, name in before}

    with pytest.raises(AssuranceStoreError, match="mandatory table missing"):
        build_durable_claim_proof_pack(
            service,
            tenant_id="tenant-a",
            finding_id=finding,
            generated_at="2026-09-01T00:00:00+00:00",
        )

    after = _schema_objects(database)
    assert after == before
    assert "causledger_change_facts" not in {name for _kind, name in after}
