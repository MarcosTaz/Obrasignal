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
EXACT_SHA = "a" * 40


def test_aviation_and_contractcredit_meet_assisted_g3_contract_only_with_runtime_proof():
    aviation = assess_recovery_vertical(
        vertical="aviation-lease-entitlement-recovery",
        pilot_path="vertical_apps/aviation_recovery/pilot.json",
        exact_source_head=EXACT_SHA,
        source_registered=True,
        verified_tests=PROOFS,
        runtime_provisioned=True,
    )
    credit = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=EXACT_SHA,
        source_registered=True,
        verified_tests=PROOFS,
        runtime_provisioned=True,
    )
    aviation.require_ready()
    credit.require_ready()
    assert aviation.ready is True
    assert credit.ready is True


def test_g3_gate_fails_closed_until_runtime_is_provisioned():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=EXACT_SHA,
        source_registered=True,
        verified_tests=PROOFS,
    )
    assert evidence.ready is False
    with pytest.raises(PilotReadinessError, match="runtime_provisioned"):
        evidence.require_ready()


def test_g3_gate_fails_closed_when_adversarial_proof_is_missing():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head=EXACT_SHA,
        source_registered=True,
        verified_tests=PROOFS - {"adversarial"},
        runtime_provisioned=True,
    )
    with pytest.raises(PilotReadinessError, match="adversarial"):
        evidence.require_ready()


def test_g3_gate_rejects_symbolic_source_ref():
    evidence = assess_recovery_vertical(
        vertical="contractcredit",
        pilot_path="vertical_apps/contractcredit/pilot.json",
        exact_source_head="main",
        source_registered=True,
        verified_tests=PROOFS,
        runtime_provisioned=True,
    )
    with pytest.raises(PilotReadinessError, match="exact_source_head"):
        evidence.require_ready()
