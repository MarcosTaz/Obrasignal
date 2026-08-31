from __future__ import annotations

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def test_durable_proof_pack_reconstructs_persisted_case_truth(tmp_path):
    service = IndustrialClaimsService(tmp_path / "claims.db")
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="customer-1",
        program_ref="program-1",
        event_ref="change-R17",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="timesheet-1",
        gross_cost="12500",
        currency="EUR",
        commercial_basis_content="PO clause and commercial basis",
        event_evidence_content="Customer requests drawing revision R17",
        cost_evidence_content="Engineering hours and rate support",
        notice_deadline_not_applicable=True,
    )
    pack = build_durable_claim_proof_pack(
        service,
        tenant_id="tenant-a",
        finding_id=result.finding.finding_id,
        generated_at="2026-08-31T22:45:00+00:00",
    )

    assert pack["brand"] == "CausLedger"
    assert pack["self_verification"]["valid"] is True
    assert pack["core_package"]["finding"]["finding_id"] == result.finding.finding_id
    assert pack["core_package"]["calculation"]["net_potential"] == "12500"
    assert len(pack["core_package"]["calculation"]["inputs"]) == 6
    assert len(pack["core_package"]["evidence_index"]) == 3
    assert pack["proof_manifest"]["attestation_target"]["sha256"]
    assert pack["external_verification_required"] is True
    assert "ORIGINAL_BYTES_NOT_INCLUDED_OR_NOT_IMMUTABLY_PERSISTED" in pack["self_verification"]["warnings"]
