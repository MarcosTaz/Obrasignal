from datetime import date

import pytest

from vertical_apps.contractcredit.intake import (
    ContractCreditPilotIntakeError,
    ContractCreditPilotIntakeService,
    EvidenceInput,
)


def _evidence(ref: str, digit: str = "a") -> EvidenceInput:
    return EvidenceInput.create(
        source_ref=ref,
        sha256=digit * 64,
        provenance=f"customer_upload:{ref}",
        authorized=True,
    )


def test_contractcredit_intake_requires_digest_provenance_and_permission():
    with pytest.raises(ContractCreditPilotIntakeError):
        EvidenceInput.create(source_ref="msa.pdf", sha256="bad", provenance="upload", authorized=True)
    with pytest.raises(ContractCreditPilotIntakeError):
        EvidenceInput.create(source_ref="msa.pdf", sha256="a" * 64, provenance="", authorized=True)
    with pytest.raises(ContractCreditPilotIntakeError):
        EvidenceInput.create(source_ref="msa.pdf", sha256="a" * 64, provenance="upload", authorized=False)


def test_service_credit_candidate_keeps_breach_entitlement_and_recovery_unproven(tmp_path):
    service = ContractCreditPilotIntakeService(tmp_path / "credit.sqlite3")
    result = service.analyze(
        tenant_id="enterprise-a",
        actor_id="analyst-a",
        service_contract=_evidence("msa.pdf", "a"),
        incident_evidence=_evidence("sev1.pdf", "b"),
        monthly_fee="50000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 15),
    )
    assert result["potential_value"] == "5000.00"
    assert result["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["breach_state"] == "NOT_ESTABLISHED"
    assert result["recovery_state"] == "NOT_ESTABLISHED"
    assert result["customer_permission_verified"] is True

    with service.service.store._connect() as conn:
        rows = conn.execute(
            "SELECT source_ref FROM evidence WHERE tenant_id=? ORDER BY source_type",
            ("enterprise-a",),
        ).fetchall()
    refs = {row["source_ref"] for row in rows}
    assert f"msa.pdf@sha256:{'a' * 64}" in refs
    assert f"sev1.pdf@sha256:{'b' * 64}" in refs


def test_zero_credit_candidate_remains_unresolved(tmp_path):
    service = ContractCreditPilotIntakeService(tmp_path / "credit.sqlite3")
    result = service.analyze(
        tenant_id="enterprise-a",
        actor_id="analyst-a",
        service_contract=_evidence("msa.pdf", "c"),
        incident_evidence=_evidence("sev1.pdf", "d"),
        monthly_fee="50000",
        credit_rate="0",
        notice_due=date(2026, 9, 15),
    )
    assert result["potential_value"] == "0"
    assert result["pilot_state"] == "EVIDENCE_OR_ECONOMICS_UNRESOLVED"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["breach_state"] == "NOT_ESTABLISHED"
    assert result["recovery_state"] == "NOT_ESTABLISHED"
