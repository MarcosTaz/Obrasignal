from datetime import date

import pytest

from vertical_apps.aviation_recovery.intake import (
    AviationPilotIntakeError,
    AviationPilotIntakeService,
    EvidenceInput,
)


def _evidence(ref: str, digit: str = "a") -> EvidenceInput:
    return EvidenceInput.create(
        source_ref=ref,
        sha256=digit * 64,
        provenance=f"customer_upload:{ref}",
        authorized=True,
    )


def test_pilot_intake_requires_content_identity_provenance_and_permission():
    with pytest.raises(AviationPilotIntakeError):
        EvidenceInput.create(source_ref="lease.pdf", sha256="bad", provenance="upload", authorized=True)
    with pytest.raises(AviationPilotIntakeError):
        EvidenceInput.create(source_ref="lease.pdf", sha256="a" * 64, provenance="", authorized=True)
    with pytest.raises(AviationPilotIntakeError):
        EvidenceInput.create(source_ref="lease.pdf", sha256="a" * 64, provenance="upload", authorized=False)


def test_evidence_backed_candidate_never_promotes_arithmetic_to_entitlement_or_recovery(tmp_path):
    service = AviationPilotIntakeService(tmp_path / "aviation.sqlite3")
    result = service.analyze(
        tenant_id="airline-a",
        actor_id="analyst-a",
        lease_contract=_evidence("lease.pdf", "a"),
        maintenance_event=_evidence("shop-visit.pdf", "b"),
        eligible_cost="100000",
        reimbursed_amount="25000",
        notice_due=date(2026, 9, 30),
    )

    assert result["potential_value"] == "75000"
    assert result["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["recovery_state"] == "NOT_ESTABLISHED"
    assert result["customer_permission_verified"] is True
    assert result["contract_evidence_sha256"] == "a" * 64
    assert result["maintenance_evidence_sha256"] == "b" * 64

    with service.service.store._connect() as conn:
        rows = conn.execute(
            "SELECT source_ref FROM evidence WHERE tenant_id=? ORDER BY source_type",
            ("airline-a",),
        ).fetchall()
    refs = {row["source_ref"] for row in rows}
    assert f"lease.pdf@sha256:{'a' * 64}" in refs
    assert f"shop-visit.pdf@sha256:{'b' * 64}" in refs


def test_zero_unreimbursed_balance_stays_unresolved_even_with_verified_documents(tmp_path):
    service = AviationPilotIntakeService(tmp_path / "aviation.sqlite3")
    result = service.analyze(
        tenant_id="airline-a",
        actor_id="analyst-a",
        lease_contract=_evidence("lease.pdf", "c"),
        maintenance_event=_evidence("shop-visit.pdf", "d"),
        eligible_cost="100000",
        reimbursed_amount="100000",
        notice_due=date(2026, 9, 30),
    )
    assert result["potential_value"] == "0"
    assert result["pilot_state"] == "EVIDENCE_OR_ECONOMICS_UNRESOLVED"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["recovery_state"] == "NOT_ESTABLISHED"
