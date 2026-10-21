import json
from pathlib import Path

from vertical_apps.industrial_claims.service import IndustrialClaimsService

FIXTURES = Path("vertical_apps/industrial_claims/synthetic_cases.json")


def test_independent_synthetic_ground_truth_cases(tmp_path):
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert data["truth_owner"] == "independent_test_fixture"
    for case in data["cases"]:
        service = IndustrialClaimsService(tmp_path / f"{case['id']}.sqlite3")
        result = service.analyze(
            tenant_id="synthetic",
            actor_id="oracle-runner",
            customer_ref="synthetic-oem",
            program_ref=case["id"],
            event_ref=f"event-{case['id']}",
            claim_family=case["claim_family"],
            commercial_basis_ref=f"basis-{case['id']}",
            cost_evidence_ref=f"cost-{case['id']}",
            gross_cost=case["gross_cost"],
            avoided_cost=case["avoided_cost"],
            resale_reuse=case["resale_reuse"],
            third_party_recovery=case["third_party_recovery"],
            prior_payment=case["prior_payment"],
            other_mitigation=case["other_mitigation"],
            missing_evidence=tuple(case["missing_evidence"]),
        )
        assert result.calculation.output_value == case["expected_net_potential"], case["id"]
        assert result.finding.state == case["expected_state"], case["id"]
