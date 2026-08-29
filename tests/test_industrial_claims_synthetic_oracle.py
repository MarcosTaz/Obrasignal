import json
from pathlib import Path

import pytest

from factory_cloud.assurance_kernel import AssuranceKernelError
from vertical_apps.industrial_claims.service import IndustrialClaimsService

FIXTURES = Path("vertical_apps/industrial_claims/synthetic_cases.json")
REQUIRED_SYNTHETIC_COMPANIES = {
    "ALPHA COMPONENTS",
    "NOVA PRECISION",
    "TITAN INDUSTRIES",
    "LEGACY PARTS",
    "DISTRESSED SUPPLIER",
    "REDTEAM INDUSTRIAL",
}


def test_independent_synthetic_ground_truth_cases(tmp_path):
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert data["truth_owner"] == "independent_test_fixture"
    assert REQUIRED_SYNTHETIC_COMPANIES <= {case["company"] for case in data["cases"]}

    for case in data["cases"]:
        service = IndustrialClaimsService(tmp_path / f"{case['id']}.sqlite3")
        kwargs = dict(
            tenant_id="synthetic",
            actor_id="oracle-runner",
            customer_ref="synthetic-oem",
            program_ref=case["id"],
            event_ref=f"event-{case['id']}",
            claim_family=case["claim_family"],
            commercial_basis_ref=f"basis-{case['id']}",
            cost_evidence_ref=f"cost-{case['id']}",
            currency="EUR",
            commercial_basis_content=f"synthetic signed commercial basis for {case['id']}",
            event_evidence_content=f"synthetic documented event for {case['id']}",
            cost_evidence_content=f"synthetic cost ledger for {case['id']}",
            gross_cost=case["gross_cost"],
            avoided_cost=case["avoided_cost"],
            resale_reuse=case["resale_reuse"],
            third_party_recovery=case["third_party_recovery"],
            prior_payment=case["prior_payment"],
            other_mitigation=case["other_mitigation"],
            notice_deadline_not_applicable=True,
            missing_evidence=tuple(case["missing_evidence"]),
        )
        if "expected_error" in case:
            with pytest.raises(AssuranceKernelError, match=case["expected_error"]):
                service.analyze(**kwargs)
            continue

        result = service.analyze(**kwargs)
        assert result.calculation.output_value == case["expected_net_potential"], case["id"]
        assert result.calculation.output_unit == "EUR", case["id"]
        assert result.finding.state == case["expected_state"], case["id"]
        assert result.notice_deadline_state == "DECLARED_NONE_FOR_REVIEW", case["id"]
        assert {item.metadata["verification_state"] for item in result.evidence} == {"CONTENT_HASHED"}
