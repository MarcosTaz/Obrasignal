from datetime import date

import pytest

from factory_cloud.assurance_kernel import AssuranceKernelError
from vertical_apps.industrial_claims.service import ALLOWED_CLAIM_FAMILIES, IndustrialClaimsService


def _base():
    return dict(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        notice_due=date(2026, 9, 30),
    )


def test_all_required_claim_families_share_net_potential_contract(tmp_path):
    for family in sorted(ALLOWED_CLAIM_FAMILIES):
        service = IndustrialClaimsService(tmp_path / f"{family}.sqlite3")
        fixture = _base()
        fixture["event_ref"] = f"event-{family}"
        fixture["cost_evidence_ref"] = f"cost-{family}"
        result = service.analyze(
            **fixture,
            claim_family=family,
            gross_cost="100000",
            avoided_cost="10000",
            resale_reuse="5000",
            third_party_recovery="2000",
            prior_payment="3000",
            other_mitigation="1000",
        )
        assert result.calculation.output_value == "79000"
        assert result.finding.state == "READY_FOR_REVIEW"
        assert result.entitlement.actionable is True
        assert result.is_new_recovery is True


def test_cost_never_becomes_money_owed_when_evidence_is_missing(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(
        **_base(),
        claim_family="WIP",
        gross_cost="50000",
        missing_evidence=("customer_authorization",),
    )
    assert result.calculation.output_value == "50000"
    assert result.entitlement.confidence == "PARTIAL"
    assert result.finding.state == "UNRESOLVED_EVIDENCE"
    with pytest.raises(Exception):
        service.review(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            reviewer="reviewer",
            approved=True,
            reason="unsupported",
        )


def test_duplicate_replay_is_marked_not_new_and_remains_idempotent(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    kwargs = dict(**_base(), claim_family="TOOLING", gross_cost="20000", prior_payment="5000")
    first = service.analyze(**kwargs)
    second = service.analyze(**kwargs)
    assert first.is_new_recovery is True
    assert second.is_new_recovery is False
    assert second.calculation.reproducibility_hash == first.calculation.reproducibility_hash


def test_same_refs_are_tenant_isolated(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    first = service.analyze(**_base(), claim_family="NRE", gross_cost="1000")
    other = dict(_base())
    other["tenant_id"] = "beta"
    second = service.analyze(**other, claim_family="NRE", gross_cost="1000")
    assert first.finding.finding_id != second.finding.finding_id
    assert first.fingerprint.fingerprint != second.fingerprint.fingerprint


def test_mitigation_over_gross_and_unknown_family_fail_closed(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    with pytest.raises(AssuranceKernelError, match="cannot exceed gross cost"):
        service.analyze(**_base(), claim_family="WIP", gross_cost="10", prior_payment="11")
    with pytest.raises(AssuranceKernelError, match="unsupported industrial claim family"):
        service.analyze(**_base(), claim_family="NOT_REAL", gross_cost="10")


def test_full_assisted_outcome_journey(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(**_base(), claim_family="EXCESS_OBSOLETE_RAW_MATERIAL", gross_cost="100000", resale_reuse="25000")
    assert service.review(tenant_id="alpha", finding_id=result.finding.finding_id, reviewer="commercial", approved=True, reason="basis and amount reviewed") == "APPROVED"
    assert service.action(tenant_id="alpha", finding_id=result.finding.finding_id) == "ACTIONED"
    outcome = service.resolve(tenant_id="alpha", finding_id=result.finding.finding_id, outcome_id="alpha:payment-1", recovered_amount="60000", currency="EUR", evidence_ref="bank-receipt-1")
    assert outcome.state == "RECOVERED"
    assert outcome.recovered_amount == "60000"
