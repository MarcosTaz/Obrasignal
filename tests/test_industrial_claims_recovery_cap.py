import pytest

from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _actioned_finding(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        claim_family="TOOLING",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="100000",
        resale_reuse="25000",
    )
    service.review(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        reviewer="commercial",
        approved=True,
        reason="reviewed net exposure",
    )
    service.action(tenant_id="alpha", finding_id=result.finding.finding_id)
    return service, result.finding.finding_id


def test_recovery_cannot_exceed_reviewed_net_potential(tmp_path):
    service, finding_id = _actioned_finding(tmp_path)

    with pytest.raises(AssuranceOperationError, match="exceeds reviewed net potential"):
        service.resolve(
            tenant_id="alpha",
            finding_id=finding_id,
            outcome_id="alpha:payment-over-cap",
            recovered_amount="75000.01",
            currency="EUR",
            evidence_ref="bank-over-cap",
        )

    assert service.ops.get_state(tenant_id="alpha", finding_id=finding_id) == "ACTIONED"
    assert service.ops.outcomes(tenant_id="alpha") == ()


def test_recovery_at_reviewed_net_potential_is_allowed(tmp_path):
    service, finding_id = _actioned_finding(tmp_path)

    outcome = service.resolve(
        tenant_id="alpha",
        finding_id=finding_id,
        outcome_id="alpha:payment-at-cap",
        recovered_amount="75000",
        currency="EUR",
        evidence_ref="bank-at-cap",
    )

    assert outcome.state == "RECOVERED"
    assert outcome.recovered_amount == "75000"
