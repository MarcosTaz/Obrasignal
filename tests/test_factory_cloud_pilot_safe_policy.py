import json
from pathlib import Path


def _policy():
    path = Path("factory_cloud/pilot_safe_policy.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_pilot_safe_policy_defines_complete_pre_customer_gate_chain():
    policy = _policy()
    gates = policy["gates"]
    assert [gate["id"] for gate in gates] == [f"PS{i}" for i in range(10)]
    required = {item for gate in gates for item in gate["required_evidence"]}
    assert {
        "end_to_end_product",
        "web_complete",
        "deterministic_calculation",
        "evidence_lineage",
        "tenant_isolation",
        "adversarial",
        "durable_recovery",
        "backup_restore",
        "observability",
        "support_continuity",
        "synthetic_company_e2e",
        "billing_sandbox",
        "shadow_validation",
        "source_registered",
        "exact_source_head",
    } <= required


def test_real_customer_is_not_allowed_to_substitute_for_pre_customer_proof():
    policy = _policy()
    forbidden = set(policy["forbidden_as_pre_customer_proof"])
    assert "real_customer" in forbidden
    assert "real_proprietary_customer_data" in forbidden
    assert "live_payment" in forbidden
    assert "customer_incident_as_qa" in forbidden


def test_commercial_exposure_is_scheduled_after_pilot_safe_blockers():
    priority = _policy()["scheduling_priority"]
    assert priority.index("pilot_safe_blocker") < priority.index("commercial_exposure_after_pilot_safe")
    assert priority.index("web_or_end_to_end_completeness") < priority.index("commercial_exposure_after_pilot_safe")
    assert priority.index("support_observability_backup") < priority.index("commercial_exposure_after_pilot_safe")
