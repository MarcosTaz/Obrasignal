from datetime import date

import pytest

from vertical_apps.aviation_recovery.intake import (
    AviationPilotIntakeError,
    AviationPilotIntakeService,
    EvidenceInput as AviationEvidence,
)
from vertical_apps.contractcredit.intake import (
    ContractCreditPilotIntakeError,
    ContractCreditPilotIntakeService,
    EvidenceInput as ContractEvidence,
)


def test_shadow_intake_rejects_missing_digest_provenance_or_permission():
    with pytest.raises(AviationPilotIntakeError):
        AviationEvidence.create(source_ref="lease.pdf", sha256="bad", provenance="public", authorized=True)
    with pytest.raises(AviationPilotIntakeError):
        AviationEvidence.create(source_ref="lease.pdf", sha256="a" * 64, provenance="", authorized=True)
    with pytest.raises(AviationPilotIntakeError):
        AviationEvidence.create(source_ref="lease.pdf", sha256="a" * 64, provenance="public", authorized=False)
    with pytest.raises(ContractCreditPilotIntakeError):
        ContractEvidence.create(source_ref="msa.pdf", sha256="a" * 64, provenance="public", authorized=False)


def test_aviation_shadow_candidate_binds_exact_evidence_without_claiming_entitlement(tmp_path):
    service = AviationPilotIntakeService(tmp_path / "aviation.sqlite3")
    result = service.analyze(
        tenant_id="shadow-airline",
        actor_id="shadow-analyst",
        lease_contract=AviationEvidence.create(source_ref="lease.pdf", sha256="a" * 64, provenance="reconstructed_public_case", authorized=True),
        maintenance_event=AviationEvidence.create(source_ref="shop.pdf", sha256="b" * 64, provenance="reconstructed_public_case", authorized=True),
        eligible_cost="100000",
        reimbursed_amount="25000",
        notice_due=date(2026, 9, 30),
    )
    assert result["potential_value"] == "75000"
    assert result["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["recovery_state"] == "NOT_ESTABLISHED"
    assert result["evidence_permission_verified"] is True
    with service.service.store._connect() as conn:
        refs = {row["source_ref"] for row in conn.execute("SELECT source_ref FROM evidence WHERE tenant_id=?", ("shadow-airline",)).fetchall()}
    assert f"lease.pdf@sha256:{'a' * 64}" in refs
    assert f"shop.pdf@sha256:{'b' * 64}" in refs


def test_contractcredit_shadow_candidate_keeps_breach_and_entitlement_unproven(tmp_path):
    service = ContractCreditPilotIntakeService(tmp_path / "credit.sqlite3")
    result = service.analyze(
        tenant_id="shadow-enterprise",
        actor_id="shadow-analyst",
        service_contract=ContractEvidence.create(source_ref="msa.pdf", sha256="c" * 64, provenance="reconstructed_public_case", authorized=True),
        incident_evidence=ContractEvidence.create(source_ref="incident.pdf", sha256="d" * 64, provenance="reconstructed_public_case", authorized=True),
        monthly_fee="50000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 15),
    )
    assert result["potential_value"] == "5000.00"
    assert result["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert result["breach_state"] == "NOT_ESTABLISHED"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["recovery_state"] == "NOT_ESTABLISHED"


def test_zero_arithmetic_never_becomes_negative_or_false_recovery_claim(tmp_path):
    aviation = AviationPilotIntakeService(tmp_path / "aviation.sqlite3")
    a = aviation.analyze(
        tenant_id="shadow-airline", actor_id="analyst",
        lease_contract=AviationEvidence.create(source_ref="lease", sha256="e" * 64, provenance="synthetic", authorized=True),
        maintenance_event=AviationEvidence.create(source_ref="event", sha256="f" * 64, provenance="synthetic", authorized=True),
        eligible_cost="100000", reimbursed_amount="100000", notice_due=date(2026, 9, 30),
    )
    assert a["potential_value"] == "0"
    assert a["pilot_state"] == "EVIDENCE_OR_ECONOMICS_UNRESOLVED"
    assert a["recovery_state"] == "NOT_ESTABLISHED"
