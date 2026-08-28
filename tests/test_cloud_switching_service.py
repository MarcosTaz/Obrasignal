from decimal import Decimal

import pytest

from cloud_switching.baseline import BaselineCost, Certainty, CurrentStateBaseline
from cloud_switching.decision import Decision
from cloud_switching.incentives import Incentive, IncentiveStatus
from cloud_switching.service import build_decision_package
from cloud_switching.synthetic import synthetic_companies

D = Decimal


def baseline_for(case):
    return CurrentStateBaseline(
        company_id="alpha-company",
        components=[
            BaselineCost(
                "total_current_run_cost",
                case.current_annual_cost,
                Certainty.KNOWN,
                source_id="billing-export-1",
            )
        ],
    )


def incentives_for(case):
    incentives = []
    if case.provider_credit_received:
        status = (
            IncentiveStatus.RECEIVED
            if case.provider_credit_received == case.provider_credit_approved
            else IncentiveStatus.PARTIALLY_RECEIVED
        )
        incentives.append(
            Incentive(
                incentive_id="provider-credit",
                program="Provider migration program",
                status=status,
                approved_amount=case.provider_credit_approved,
                received_amount=case.provider_credit_received,
                approval_evidence_id="provider-approval",
                receipt_evidence_id="provider-receipt",
            )
        )
    if case.partner_incentive_received:
        status = (
            IncentiveStatus.RECEIVED
            if case.partner_incentive_received == case.partner_incentive_approved
            else IncentiveStatus.PARTIALLY_RECEIVED
        )
        incentives.append(
            Incentive(
                incentive_id="partner-credit",
                program="Partner funding",
                status=status,
                approved_amount=case.partner_incentive_approved,
                received_amount=case.partner_incentive_received,
                approval_evidence_id="partner-approval",
                receipt_evidence_id="partner-receipt",
            )
        )
    return incentives


def test_assisted_package_reconciles_baseline_incentives_and_decision():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    package = build_decision_package(baseline_for(case), case, incentives_for(case))
    assert package.decision is Decision.SWITCH
    assert package.baseline_annual_cost == case.current_annual_cost
    assert package.captured_incentives == D("30000")
    assert package.gross_switching_cost == D("100000")
    assert package.customer_cash_switching_cost == D("70000")
    assert "billing-export-1" in package.audit_evidence_ids
    assert "provider-receipt" in package.audit_evidence_ids


def test_decision_package_fails_if_incentive_ledger_does_not_reconcile():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    with pytest.raises(ValueError):
        build_decision_package(baseline_for(case), case, [])


def test_missing_material_input_survives_into_package_without_fake_economics():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    baseline = CurrentStateBaseline(
        company_id="alpha-company",
        components=[BaselineCost("license", None, Certainty.UNKNOWN)],
    )
    package = build_decision_package(baseline, case, incentives_for(case))
    assert package.decision is Decision.NEEDS_MORE_EVIDENCE
    assert package.gross_switching_cost is None
    assert package.unresolved_material_inputs == ("license",)
