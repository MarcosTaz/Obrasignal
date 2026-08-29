import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _analyze(service, *, gross_cost="100000", currency="EUR"):
    return service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        claim_family="TOOLING",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        currency=currency,
        commercial_basis_content="signed tooling commercial basis",
        event_evidence_content="documented customer cancellation",
        cost_evidence_content=f"tooling ledger supporting gross cost {gross_cost}",
        gross_cost=gross_cost,
        resale_reuse="25000",
        notice_deadline_not_applicable=True,
    )


def test_duplicate_analysis_does_not_downgrade_recovered_finding(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    first = _analyze(service)
    service.review(
        tenant_id="alpha",
        finding_id=first.finding.finding_id,
        reviewer="commercial-reviewer",
        approved=True,
        reason="reviewed evidence and amount",
    )
    service.action(tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="operator")
    service.resolve(
        tenant_id="alpha",
        finding_id=first.finding.finding_id,
        outcome_id="alpha:payment-1",
        recovered_amount="70000",
        currency="EUR",
        evidence_ref="bank-1",
        actor_id="operator",
    )

    replay = _analyze(service)

    assert replay.is_new_recovery is False
    assert replay.finding.state == "RECOVERED"
    assert replay.finding.reviewer == "commercial-reviewer"
    assert replay.finding.decision_reason == "reviewed evidence and amount"
    assert replay.notice_deadline_state == "VERIFIED_NONE"
    assert replay.calculation.output_unit == "EUR"
    assert service.ops.get_state(tenant_id="alpha", finding_id=first.finding.finding_id) == "RECOVERED"
    assert len(service.ops.outcomes(tenant_id="alpha")) == 1


def test_duplicate_analysis_with_changed_economic_input_fails_closed(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    first = _analyze(service)
    service.review(
        tenant_id="alpha",
        finding_id=first.finding.finding_id,
        reviewer="commercial-reviewer",
        approved=True,
        reason="reviewed evidence and amount",
    )

    with pytest.raises(AssuranceStoreError, match="immutable evidence id collision|immutable calculation id collision"):
        _analyze(service, gross_cost="110000")

    assert service.ops.get_state(tenant_id="alpha", finding_id=first.finding.finding_id) == "APPROVED"


def test_duplicate_analysis_cannot_rewrite_currency(tmp_path):
    service = IndustrialClaimsService(tmp_path / "currency-replay.sqlite3")
    first = _analyze(service)

    with pytest.raises(AssuranceStoreError, match="immutable calculation id collision"):
        _analyze(service, currency="USD")

    assert service.ops.get_state(tenant_id="alpha", finding_id=first.finding.finding_id) == "READY_FOR_REVIEW"
