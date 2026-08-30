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


def test_synthetic_candidate_requires_human_review_before_action_and_durable_recovery_outcome(tmp_path):
    service = AviationPilotIntakeService(tmp_path / "aviation.sqlite3")
    result = service.analyze(
        tenant_id="synthetic-airline",
        actor_id="synthetic-analyst",
        lease_contract=_evidence("synthetic-lease.pdf", "e"),
        maintenance_event=_evidence("synthetic-shop-visit.pdf", "f"),
        eligible_cost="125000",
        reimbursed_amount="25000",
        notice_due=date(2026, 10, 15),
    )

    finding_id = result["finding_id"]
    assert result["pilot_state"] == "CANDIDATE_READY_FOR_HUMAN_REVIEW"
    assert result["entitlement_state"] == "UNKNOWN"
    assert result["recovery_state"] == "NOT_ESTABLISHED"

    assert service.review(
        tenant_id="synthetic-airline",
        finding_id=finding_id,
        reviewer="synthetic-human-reviewer",
        approved=True,
        reason="synthetic fixture: evidence and arithmetic accepted for workflow testing only",
    ) == "APPROVED"
    assert service.action(tenant_id="synthetic-airline", finding_id=finding_id) == "ACTIONED"

    outcome = service.resolve(
        tenant_id="synthetic-airline",
        finding_id=finding_id,
        outcome_id="synthetic-outcome-recovered",
        recovered_amount="40000",
        currency="USD",
        evidence_ref="synthetic-settlement-proof@sha256:" + "1" * 64,
    )
    assert outcome.state == "RECOVERED"
    assert outcome.recovered_amount == "40000"
    assert service.service.ops.get_state(tenant_id="synthetic-airline", finding_id=finding_id) == "RECOVERED"


def test_synthetic_action_can_close_with_zero_recovery_without_fabricating_value(tmp_path):
    service = AviationPilotIntakeService(tmp_path / "aviation-no-recovery.sqlite3")
    result = service.analyze(
        tenant_id="synthetic-airline-no-recovery",
        actor_id="synthetic-analyst",
        lease_contract=_evidence("synthetic-lease-no-recovery.pdf", "2"),
        maintenance_event=_evidence("synthetic-event-no-recovery.pdf", "3"),
        eligible_cost="90000",
        reimbursed_amount="10000",
        notice_due=date(2026, 10, 15),
    )
    finding_id = result["finding_id"]

    service.review(
        tenant_id="synthetic-airline-no-recovery",
        finding_id=finding_id,
        reviewer="synthetic-human-reviewer",
        approved=True,
        reason="synthetic fixture: allow action-path test without asserting entitlement",
    )
    service.action(tenant_id="synthetic-airline-no-recovery", finding_id=finding_id)
    outcome = service.resolve(
        tenant_id="synthetic-airline-no-recovery",
        finding_id=finding_id,
        outcome_id="synthetic-outcome-zero",
        recovered_amount="0",
        currency="USD",
        evidence_ref="synthetic-no-recovery-proof@sha256:" + "4" * 64,
    )

    assert outcome.state == "CLOSED_NO_RECOVERY"
    assert outcome.recovered_amount == "0"
    assert service.service.ops.get_state(
        tenant_id="synthetic-airline-no-recovery", finding_id=finding_id
    ) == "CLOSED_NO_RECOVERY"
