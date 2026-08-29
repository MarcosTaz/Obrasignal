from earnedcash.ledger import reconcile_ledger
from earnedcash.synthetic import diversified_companies


def test_diversified_synthetic_companies_match_independent_oracle():
    companies = diversified_companies()
    assert len(companies) == 6
    for company in companies:
        result = reconcile_ledger(company.records)
        assert result.verified_cash == company.oracle_verified_cash, company.name
        assert result.due_unpaid == company.oracle_due_unpaid, company.name
        assert result.not_yet_due == company.oracle_not_yet_due, company.name
        assert result.unknown_value == company.oracle_unknown, company.name
        assert result.p0_count == company.oracle_p0, company.name
