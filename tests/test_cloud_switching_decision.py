from decimal import Decimal

from cloud_switching.baseline import BaselineCost, Certainty, CurrentStateBaseline
from cloud_switching.decision import Decision, decide
from cloud_switching.synthetic import synthetic_companies

D = Decimal


def baseline_for(cost: Decimal) -> CurrentStateBaseline:
    return CurrentStateBaseline(
        company_id="company",
        components=[BaselineCost("total_current_run_cost", cost, Certainty.KNOWN, source_id="billing-export")],
    )


def test_large_savings_case_can_recommend_switch():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    result = decide(baseline_for(case.current_annual_cost), case)
    assert result.decision is Decision.SWITCH


def test_negative_value_case_recommends_do_not_switch():
    case = synthetic_companies()["titan_enterprise"].case
    result = decide(baseline_for(case.current_annual_cost), case)
    assert result.decision is Decision.DO_NOT_SWITCH_NOW


def test_small_savings_case_can_recommend_temporary_renewal():
    case = synthetic_companies()["nova_services"].case
    result = decide(baseline_for(case.current_annual_cost), case, maximum_payback_months=D("24"))
    assert result.decision is Decision.RENEW_TEMPORARILY


def test_missing_material_baseline_requires_more_evidence():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    baseline = CurrentStateBaseline(
        company_id="company",
        components=[BaselineCost("license", None, Certainty.UNKNOWN)],
    )
    result = decide(baseline, case)
    assert result.decision is Decision.NEEDS_MORE_EVIDENCE
    assert result.economics is None


def test_unreconciled_baseline_requires_more_evidence():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    result = decide(baseline_for(D("1")), case)
    assert result.decision is Decision.NEEDS_MORE_EVIDENCE
