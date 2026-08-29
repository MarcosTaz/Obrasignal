import pytest

from factory_cloud.pilot_readiness import PilotReadinessError, assess_recovery_vertical

PROOFS = {
    "deterministic_calculation",
    "evidence_lineage",
    "tenant_isolation",
    "durable_recovery",
    "adversarial",
    "assisted_api",
}
HEAD = "0ce7dffe58140a51751c3c114d43f3af90fb5be6"


def test_aviation_and_contractcredit_meet_assisted_g3_contract():
    aviation = assess_recovery_vertical(
        vertical="aviation-lease-entitlement-recovery",
        pilot_path="vertical_apps/aviation_recovery/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=PROOFS,
    )
    credit = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=PROOFS,
    )
    aviation.require_ready()
    credit.require_ready()
    assert aviation.ready is True
    assert credit.ready is True


def test_g3_gate_fails_closed_when_adversarial_proof_is_missing():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=HEAD,
        source_registered=True,
        verified_tests=PROOFS - {"adversarial"},
    )
    with pytest.raises(PilotReadinessError, match="adversarial"):
        evidence.require_ready()
