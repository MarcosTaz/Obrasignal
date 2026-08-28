from cloud_switching.domain import calculate
from cloud_switching.oracle import oracle_calculate
from cloud_switching.synthetic import synthetic_companies


def test_synthetic_cases_match_independent_oracle():
    for company in synthetic_companies().values():
        product = calculate(company.case)
        oracle = oracle_calculate(company.case)
        assert product.gross_switching_cost == oracle.gross_switching_cost
        assert product.received_capital == oracle.received_capital
        assert product.customer_cash_switching_cost == oracle.customer_cash_switching_cost
        assert product.annual_status_quo_avoidance == oracle.annual_status_quo_avoidance
        assert product.economic_payback_months == oracle.economic_payback_months
        assert product.customer_cash_payback_months == oracle.customer_cash_payback_months


def test_negative_and_neutral_synthetic_cases_have_no_payback():
    companies = synthetic_companies()
    for key in ("titan_enterprise", "hybrid_europe"):
        result = calculate(companies[key].case)
        assert result.annual_status_quo_avoidance <= 0
        assert result.economic_payback_months is None
        assert result.customer_cash_payback_months is None


def test_factory_contains_both_migrate_and_do_not_migrate_ground_truth():
    decisions = {company.oracle_should_migrate for company in synthetic_companies().values()}
    assert decisions == {True, False}
