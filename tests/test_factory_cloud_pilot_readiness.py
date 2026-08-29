import pytest

from factory_cloud.pilot_readiness import PilotReadinessError, assess_recovery_vertical

CORE_PROOFS = {
    "deterministic_calculation",
    "evidence_lineage",
    "tenant_isolation",
    "durable_recovery",
    "adversarial",
    "assisted_api",
}
PILOT_SAFE_PROOFS = CORE_PROOFS | {
    "end_to_end_product",
    "web_complete",
    "backup_restore",
    "observability",
    "support_continuity",
    "billing_sandbox",
    "synthetic_company_e2e",
    "shadow_validation",
}
HEAD = "0ce7dffe58140a51751c3c114d43f3af90fb5be6"


def test_complete_pre_customer_proof_can_reach_pilot_safe():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=PILOT_SAFE_PROOFS,
    )
    evidence.require_ready()
    assert evidence.ready is True
    assert evidence.classification == "PILOT_SAFE"


def test_legacy_assisted_g3_proof_is_not_enough_for_real_pilot():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=CORE_PROOFS,
    )
    assert evidence.ready is False
    assert evidence.classification == "NOT_PILOT_SAFE"
    assert set(evidence.missing_proofs()) >= {
        "end_to_end_product",
        "web_complete",
        "backup_restore",
        "observability",
        "support_continuity",
        "billing_sandbox",
        "synthetic_company_e2e",
        "shadow_validation",
    }
    with pytest.raises(PilotReadinessError, match="pilot-safe readiness incomplete"):
        evidence.require_ready()


def test_pilot_safe_gate_fails_closed_when_adversarial_proof_is_missing():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=PILOT_SAFE_PROOFS - {"adversarial"},
    )
    with pytest.raises(PilotReadinessError, match="adversarial_tests"):
        evidence.require_ready()


def test_pilot_safe_gate_rejects_symbolic_source_ref():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head="main",
        source_registered=True,
        verified_tests=PILOT_SAFE_PROOFS,
    )
    with pytest.raises(PilotReadinessError, match="exact_source_head"):
        evidence.require_ready()


def test_real_customer_or_payment_is_not_a_pilot_safe_proof_token():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=CORE_PROOFS | {"real_customer", "real_payment"},
    )
    assert evidence.ready is False
    assert "synthetic_company_e2e" in evidence.missing_proofs()
    assert "shadow_validation" in evidence.missing_proofs()
