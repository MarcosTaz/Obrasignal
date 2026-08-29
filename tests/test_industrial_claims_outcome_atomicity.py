import pytest

from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _reviewed_not_actioned(service: IndustrialClaimsService):
    result = service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="outcome-atomic",
        claim_family="TOOLING",
        commercial_basis_ref="basis-outcome-atomic",
        cost_evidence_ref="cost-outcome-atomic",
        currency="EUR",
        commercial_basis_content="signed tooling settlement terms",
        event_evidence_content="documented cancellation event",
        cost_evidence_content="tooling cost ledger",
        gross_cost="10000",
        notice_deadline_not_applicable=True,
    )
    service.review(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        reviewer="reviewer",
        approved=True,
        reason="documented candidate reviewed",
    )
    return result


def test_outcome_document_rolls_back_if_state_transition_fails(tmp_path):
    service = IndustrialClaimsService(tmp_path / "outcome-atomic.sqlite3")
    result = _reviewed_not_actioned(service)
    before_evidence = service.store.count("evidence", "alpha")

    with pytest.raises(AssuranceOperationError, match="only actioned findings"):
        service.resolve(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            outcome_id="alpha:premature-outcome",
            recovered_amount="5000",
            currency="EUR",
            evidence_ref="bank-premature",
            evidence_content="bank document that must roll back with failed transition",
            actor_id="operator",
        )

    assert service.store.count("evidence", "alpha") == before_evidence
    assert service.ops.outcomes(tenant_id="alpha") == ()
    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "APPROVED"


def test_outcome_document_and_state_commit_together(tmp_path):
    service = IndustrialClaimsService(tmp_path / "outcome-success.sqlite3")
    result = _reviewed_not_actioned(service)
    service.action(tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="operator")

    outcome = service.resolve(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        outcome_id="alpha:settlement",
        recovered_amount="5000",
        currency="EUR",
        evidence_ref="bank-settlement",
        evidence_content="verified settlement receipt for 5000 EUR",
        actor_id="operator",
    )

    assert outcome.state == "RECOVERED"
    assert service.store.count("evidence", "alpha") == 4
    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "RECOVERED"
    assert len(service.ops.outcomes(tenant_id="alpha")) == 1
