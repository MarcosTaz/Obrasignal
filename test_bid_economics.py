from datetime import datetime, timezone
from decimal import Decimal

import pytest

from bid_economics import (
    BidEconomicsInput,
    CostCategory,
    CostComponent,
    CostNature,
    EconomicValue,
    GuaranteeExposure,
    InputBasis,
    Money,
    PaymentTerm,
    PaymentTerms,
    RevenueBasis,
    Scenario,
    ScenarioMoney,
    evaluate_bid_economics,
    margin_percent,
    markup_percent,
    recalculate_bid_economics,
    target_margin_price,
)

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def sm(minimum, probable=None, prudent=None, currency="EUR"):
    probable = minimum if probable is None else probable
    prudent = probable if prudent is None else prudent
    return ScenarioMoney(Money(minimum, currency), Money(probable, currency), Money(prudent, currency))


def component(category, nature, minimum, probable=None, prudent=None, currency="EUR", basis=InputBasis.ESTIMATE):
    return CostComponent(category, nature, sm(minimum, probable, prudent, currency), basis)


def base_input(**overrides):
    data = dict(
        opportunity_id="opp-1",
        tenant_id="tenant-a",
        currency="EUR",
        revenue=EconomicValue(Money("125", "EUR"), InputBasis.FACT, "bid price"),
        revenue_basis=RevenueBasis.BID_PRICE,
        cost_components=(component(CostCategory.MATERIAL, CostNature.DIRECT, "100"),),
        guarantees=(GuaranteeExposure("PERFORMANCE", EconomicValue(Money("20", "EUR"), InputBasis.FACT)),),
        payment_terms=PaymentTerms(PaymentTerm.NET30),
        duration_months=Decimal("1"),
        target_margin_percent=Decimal("20"),
    )
    data.update(overrides)
    return BidEconomicsInput(**data)


def scenario(assessment, name):
    return next(x for x in assessment.scenarios if x.scenario == name)


def test_markup_25_margin_20():
    revenue = Money("125", "EUR")
    cost = Money("100", "EUR")
    profit = revenue - cost
    assert markup_percent(profit, cost) == Decimal("25.00")
    assert margin_percent(profit, revenue) == Decimal("20.0")


def test_break_even_margin_zero():
    data = base_input(revenue=EconomicValue(Money("100", "EUR"), InputBasis.FACT), target_margin_percent=None)
    result = scenario(evaluate_bid_economics(data, generated_at=NOW), Scenario.PROBABLE)
    assert result.gross_profit == Money("0", "EUR")
    assert result.gross_margin_percent == Decimal("0")
    assert result.economic_break_even_price == Money("100", "EUR")


def test_target_margin_price_formula():
    assert target_margin_price(Money("100", "EUR"), Decimal("20")) == Money("125", "EUR")


def test_unknown_cost_is_not_zero_and_blocks_margin():
    unknown = CostComponent(CostCategory.LABOUR, CostNature.DIRECT, None, InputBasis.UNKNOWN)
    data = base_input(cost_components=(component(CostCategory.MATERIAL, CostNature.DIRECT, "100"), unknown))
    assessment = evaluate_bid_economics(data, generated_at=NOW)
    probable = scenario(assessment, Scenario.PROBABLE)
    assert probable.execution_cost is None
    assert probable.gross_profit is None
    assert probable.gross_margin_percent is None
    assert "COST:LABOUR" in assessment.missing_inputs


def test_zero_is_known_zero_not_unknown():
    zero = component(CostCategory.OTHER, CostNature.INDIRECT, "0", basis=InputBasis.FACT)
    data = base_input(cost_components=(component(CostCategory.MATERIAL, CostNature.DIRECT, "100"), zero))
    probable = scenario(evaluate_bid_economics(data, generated_at=NOW), Scenario.PROBABLE)
    assert probable.execution_cost == Money("100", "EUR")


def test_multi_currency_is_rejected_not_summed():
    data = base_input(cost_components=(component(CostCategory.MATERIAL, CostNature.DIRECT, "100", currency="GBP"),))
    with pytest.raises(ValueError, match="MULTI_CURRENCY_UNRESOLVED"):
        evaluate_bid_economics(data, generated_at=NOW)


def test_money_rejects_nan_infinity_and_bad_currency():
    for bad in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValueError):
            Money(bad, "EUR")
    with pytest.raises(ValueError):
        Money("1", "EURO")


def test_negative_cost_rejected():
    with pytest.raises(ValueError):
        sm("-1")


def test_prudent_cost_cannot_be_below_probable():
    with pytest.raises(ValueError):
        sm("90", "100", "99")


def test_payment_lag_monotonically_increases_peak_cash_requirement():
    data = base_input(
        revenue=EconomicValue(Money("1000", "EUR"), InputBasis.FACT),
        cost_components=(component(CostCategory.LABOUR, CostNature.DIRECT, "600"),),
        duration_months=Decimal("6"),
        payment_terms=PaymentTerms(PaymentTerm.NET30),
    )
    net30 = scenario(evaluate_bid_economics(data, generated_at=NOW), Scenario.PROBABLE).working_capital_requirement
    net90 = scenario(recalculate_bid_economics(data, payment_days=90, generated_at=NOW), Scenario.PROBABLE).working_capital_requirement
    assert net30 == Money("100", "EUR")
    assert net90 == Money("300", "EUR")
    assert net90.amount >= net30.amount


def test_advance_payment_reduces_cash_exposure():
    common = dict(
        revenue=EconomicValue(Money("1000", "EUR"), InputBasis.FACT),
        cost_components=(component(CostCategory.LABOUR, CostNature.DIRECT, "600"),),
        duration_months=Decimal("6"),
    )
    no_advance = base_input(**common, payment_terms=PaymentTerms(PaymentTerm.NET90))
    advance = base_input(**common, payment_terms=PaymentTerms(PaymentTerm.NET90, advance_percent=Decimal("10")))
    wc1 = scenario(evaluate_bid_economics(no_advance, generated_at=NOW), Scenario.PROBABLE).working_capital_requirement
    wc2 = scenario(evaluate_bid_economics(advance, generated_at=NOW), Scenario.PROBABLE).working_capital_requirement
    assert wc2.amount < wc1.amount


def test_retention_delays_cash_without_increasing_revenue():
    data = base_input(
        revenue=EconomicValue(Money("1000", "EUR"), InputBasis.FACT),
        cost_components=(component(CostCategory.LABOUR, CostNature.DIRECT, "600"),),
        duration_months=Decimal("6"),
        payment_terms=PaymentTerms(PaymentTerm.NET30, retention_percent=Decimal("5")),
    )
    assessment = evaluate_bid_economics(data, generated_at=NOW)
    probable = scenario(assessment, Scenario.PROBABLE)
    assert assessment.revenue.money == Money("1000", "EUR")
    assert probable.working_capital_requirement == Money("150", "EUR")


def test_guarantee_exposure_is_not_project_cost_and_fee_is_separate():
    guarantee = GuaranteeExposure(
        "PERFORMANCE",
        EconomicValue(Money("500", "EUR"), InputBasis.FACT),
        EconomicValue(Money("5", "EUR"), InputBasis.ESTIMATE),
    )
    data = base_input(guarantees=(guarantee,))
    assessment = evaluate_bid_economics(data, generated_at=NOW)
    probable = scenario(assessment, Scenario.PROBABLE)
    assert assessment.bonding_exposure == Money("500", "EUR")
    assert assessment.bonding_fees == Money("5", "EUR")
    assert probable.execution_cost == Money("100", "EUR")


def test_bid_preparation_cost_is_separate_from_execution_cost():
    costs = (
        component(CostCategory.MATERIAL, CostNature.DIRECT, "100"),
        component(CostCategory.OTHER, CostNature.BID_PREPARATION, "7"),
    )
    probable = scenario(evaluate_bid_economics(base_input(cost_components=costs), generated_at=NOW), Scenario.PROBABLE)
    assert probable.execution_cost == Money("100", "EUR")
    assert probable.bid_preparation_cost == Money("7", "EUR")


def test_scenario_order_and_negative_prudent_margin_warning():
    costs = (component(CostCategory.MATERIAL, CostNature.DIRECT, "80", "100", "140"),)
    assessment = evaluate_bid_economics(base_input(cost_components=costs), generated_at=NOW)
    minimum = scenario(assessment, Scenario.MINIMUM)
    probable = scenario(assessment, Scenario.PROBABLE)
    prudent = scenario(assessment, Scenario.PRUDENT)
    assert minimum.execution_cost.amount <= probable.execution_cost.amount <= prudent.execution_cost.amount
    assert prudent.gross_margin_percent < 0
    assert "NEGATIVE_PRUDENT_MARGIN" in assessment.warnings


def test_material_what_if_changes_cost_and_preserves_structured_assumption():
    result = recalculate_bid_economics(base_input(), material_multiplier="1.10", generated_at=NOW)
    probable = scenario(result, Scenario.PROBABLE)
    assert probable.execution_cost == Money("110.0", "EUR")
    assert "WHAT_IF_OVERRIDE" in result.assumptions


def test_published_value_is_labeled_not_claimed_as_guaranteed_revenue():
    data = base_input(revenue_basis=RevenueBasis.PUBLISHED_ESTIMATED_VALUE)
    result = evaluate_bid_economics(data, generated_at=NOW)
    assert result.revenue_basis == RevenueBasis.PUBLISHED_ESTIMATED_VALUE


def test_missing_revenue_does_not_fabricate_margin():
    data = base_input(revenue=EconomicValue(None), revenue_basis=RevenueBasis.UNKNOWN)
    result = scenario(evaluate_bid_economics(data, generated_at=NOW), Scenario.PROBABLE)
    assert result.gross_profit is None
    assert result.gross_margin_percent is None


def test_zero_revenue_margin_is_undefined():
    data = base_input(revenue=EconomicValue(Money("0", "EUR"), InputBasis.FACT))
    result = scenario(evaluate_bid_economics(data, generated_at=NOW), Scenario.PROBABLE)
    assert result.gross_margin_percent is None


def test_assessment_is_deterministic_with_injected_clock():
    data = base_input()
    left = evaluate_bid_economics(data, generated_at=NOW)
    right = evaluate_bid_economics(data, generated_at=NOW)
    assert left == right
    assert left.input_fingerprint == right.input_fingerprint


def test_tenant_inputs_are_isolated_by_contract_and_fingerprint():
    a = evaluate_bid_economics(base_input(tenant_id="tenant-a"), generated_at=NOW)
    b = evaluate_bid_economics(base_input(tenant_id="tenant-b"), generated_at=NOW)
    assert a.tenant_id == "tenant-a"
    assert b.tenant_id == "tenant-b"
    assert a.input_fingerprint != b.input_fingerprint


def test_engine_makes_no_go_no_go_decision():
    assessment = evaluate_bid_economics(
        base_input(cost_components=(component(CostCategory.MATERIAL, CostNature.DIRECT, "200"),)),
        generated_at=NOW,
    )
    assert "NO_BID" not in repr(assessment)
    assert "PURSUE" not in repr(assessment)


def test_large_decimal_keeps_precision_without_float_rounding():
    huge = Decimal("999999999999999999999999.123456789")
    data = base_input(
        revenue=EconomicValue(Money(huge + Decimal("1"), "EUR"), InputBasis.FACT),
        cost_components=(component(CostCategory.MATERIAL, CostNature.DIRECT, huge),),
    )
    probable = scenario(evaluate_bid_economics(data, generated_at=NOW), Scenario.PROBABLE)
    assert probable.gross_profit == Money("1", "EUR")
