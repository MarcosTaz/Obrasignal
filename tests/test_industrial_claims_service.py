from datetime import date

import pytest

from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.service import (
    ALLOWED_CLAIM_FAMILIES,
    CLAIM_CURRENCY_EVIDENCE,
    COMMERCIAL_BASIS_DOCUMENT,
    COST_DOCUMENT,
    EVENT_DOCUMENT,
    NOTICE_DEADLINE_EVIDENCE,
    IndustrialClaimsService,
)


def _base():
    return dict(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        currency="EUR",
        commercial_basis_content="signed supply agreement clause and purchase order terms",
        event_evidence_content="customer cancellation notice for program-1",
        cost_evidence_content="inventory and cost ledger supporting the stated exposure",
        notice_due=date(2026, 9, 30),
    )


def test_all_required_claim_families_share_net_potential_contract(tmp_path):
    for family in sorted(ALLOWED_CLAIM_FAMILIES):
        service = IndustrialClaimsService(tmp_path / f"{family}.sqlite3")
        fixture = _base()
        fixture["event_ref"] = f"event-{family}"
        fixture["cost_evidence_ref"] = f"cost-{family}"
        fixture["event_evidence_content"] = f"documented commercial event for {family}"
        fixture["cost_evidence_content"] = f"documented cost ledger for {family}"
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
        assert result.calculation.output_unit == "EUR"
        assert {item.unit for item in result.calculation.inputs} == {"EUR"}
        assert result.finding.state == "READY_FOR_REVIEW"
        assert result.entitlement.actionable is True
        assert result.entitlement.rule_ref == "documented-commercial-basis-v2"
        assert result.notice_deadline_state == "VERIFIED_DATE"
        assert {item.metadata["verification_state"] for item in result.evidence} == {"CONTENT_HASHED"}
        assert result.is_new_recovery is True


def test_missing_claim_currency_stays_unresolved_and_invalid_code_fails_closed(tmp_path):
    service = IndustrialClaimsService(tmp_path / "currency.sqlite3")
    base = _base()
    base.pop("currency")
    result = service.analyze(**base, claim_family="TOOLING", gross_cost="50000")

    assert result.finding.state == "UNRESOLVED_EVIDENCE"
    assert result.calculation.output_unit == "UNKNOWN"
    assert CLAIM_CURRENCY_EVIDENCE in result.missing_evidence

    invalid = _base()
    invalid["event_ref"] = "invalid-currency"
    with pytest.raises(AssuranceKernelError, match="three-letter ASCII"):
        service.analyze(**invalid, claim_family="TOOLING", gross_cost="50000", currency="EURO")


def test_reference_only_sources_never_become_review_ready(tmp_path):
    service = IndustrialClaimsService(tmp_path / "reference-only.sqlite3")
    base = _base()
    base.pop("commercial_basis_content")
    base.pop("event_evidence_content")
    base.pop("cost_evidence_content")

    result = service.analyze(**base, claim_family="TOOLING", gross_cost="50000")

    assert result.finding.state == "UNRESOLVED_EVIDENCE"
    assert result.entitlement.confidence == "PARTIAL"
    assert {COMMERCIAL_BASIS_DOCUMENT, EVENT_DOCUMENT, COST_DOCUMENT} <= set(result.missing_evidence)
    assert {item.metadata["verification_state"] for item in result.evidence} == {"REFERENCE_ONLY"}
    with pytest.raises(AssuranceOperationError, match="not ready for review"):
        service.review(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            reviewer="reviewer",
            approved=True,
            reason="references are not documentary proof",
        )


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


def test_unknown_notice_deadline_fails_closed_until_date_or_verified_none(tmp_path):
    service = IndustrialClaimsService(tmp_path / "unknown-deadline.sqlite3")
    base = _base()
    base.pop("notice_due")
    result = service.analyze(**base, claim_family="TOOLING", gross_cost="50000")

    assert result.notice_deadline_state == "UNKNOWN"
    assert NOTICE_DEADLINE_EVIDENCE in result.missing_evidence
    assert result.entitlement.confidence == "PARTIAL"
    assert result.finding.state == "UNRESOLVED_EVIDENCE"
    with pytest.raises(Exception):
        service.review(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            reviewer="reviewer",
            approved=True,
            reason="deadline unknown",
        )

    verified_none_service = IndustrialClaimsService(tmp_path / "verified-none.sqlite3")
    verified_none = verified_none_service.analyze(
        **base,
        claim_family="TOOLING",
        gross_cost="50000",
        notice_deadline_not_applicable=True,
    )
    assert verified_none.notice_deadline_state == "VERIFIED_NONE"
    assert NOTICE_DEADLINE_EVIDENCE not in verified_none.missing_evidence
    assert verified_none.finding.state == "READY_FOR_REVIEW"


def test_notice_date_and_verified_none_are_mutually_exclusive(tmp_path):
    service = IndustrialClaimsService(tmp_path / "conflicting-deadline.sqlite3")
    with pytest.raises(AssuranceKernelError, match="mutually exclusive"):
        service.analyze(
            **_base(),
            claim_family="WIP",
            gross_cost="100",
            notice_deadline_not_applicable=True,
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


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_industrial_economics_fail_closed(tmp_path, value):
    service = IndustrialClaimsService(tmp_path / f"non-finite-{value}.sqlite3")
    with pytest.raises(AssuranceKernelError, match="finite decimals"):
        service.analyze(**_base(), claim_family="WIP", gross_cost=value)

    with pytest.raises(AssuranceKernelError, match="finite decimals"):
        service.analyze(**_base(), claim_family="WIP", gross_cost="100", prior_payment=value)


def test_creator_cannot_self_review_even_with_direct_service_access(tmp_path):
    service = IndustrialClaimsService(tmp_path / "four-eyes.sqlite3")
    result = service.analyze(**_base(), claim_family="TOOLING", gross_cost="50000")

    with pytest.raises(AssuranceOperationError, match="independent"):
        service.review(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            reviewer="analyst",
            approved=True,
            reason="self approval must fail",
        )

    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "READY_FOR_REVIEW"


def test_full_assisted_outcome_journey(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(**_base(), claim_family="EXCESS_OBSOLETE_RAW_MATERIAL", gross_cost="100000", resale_reuse="25000")
    assert service.review(tenant_id="alpha", finding_id=result.finding.finding_id, reviewer="commercial", approved=True, reason="basis and amount reviewed") == "APPROVED"
    assert service.action(tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="operator") == "ACTIONED"
    outcome = service.resolve(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        outcome_id="alpha:payment-1",
        recovered_amount="60000",
        currency="EUR",
        evidence_ref="bank-receipt-1",
        actor_id="operator",
    )
    assert outcome.state == "RECOVERED"
    assert outcome.recovered_amount == "60000"
    assert outcome.currency == "EUR"
