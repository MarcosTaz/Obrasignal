import pytest

from vertical_apps.industrial_claims.leakage_reconciliation import reconcile_recovery_ledger
from vertical_apps.industrial_claims.recovery_portfolio import RecoveryPortfolioError, rollup_recovery_portfolio
from vertical_apps.industrial_claims.recovery_reconciliation_store import RecoveryReconciliationStore


def _record(store, *, tenant, finding, documented, supported, claimed, approved, settled, currency="EUR"):
    snapshot = reconcile_recovery_ledger(
        documented_cost=documented, mitigation="0", evidence_supported=supported,
        claimed=claimed, approved=approved, settled=settled, currency=currency,
    )
    return store.append(
        tenant_id=tenant, finding_id=finding, snapshot=snapshot,
        actor_id="portfolio-reviewer", evidence_ref=f"pack-{finding}",
    )


def test_portfolio_rollup_sums_latest_case_truth_without_double_count(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "portfolio.sqlite3")
    first = _record(store, tenant="alpha", finding="finding-a", documented="100", supported="80", claimed="60", approved="50", settled="40")
    second = _record(store, tenant="alpha", finding="finding-b", documented="200", supported="150", claimed="120", approved="100", settled="70")
    rollup = rollup_recovery_portfolio(tenant_id="alpha", records=(first, second))
    assert rollup.case_count == 2
    assert rollup.currency == "EUR"
    assert rollup.amounts["net_documented_exposure"] == 300
    assert rollup.amounts["evidence_supported"] == 230
    assert rollup.amounts["supported_unclaimed"] == 50
    assert rollup.amounts["claimed_unapproved"] == 30
    assert rollup.amounts["approved_unsettled"] == 40
    assert rollup.amounts["supported_unsettled"] == 120
    assert len(rollup.portfolio_hash) == 64
    assert rollup.as_dict()["cross_currency_aggregation_performed"] is False
    assert rollup.as_dict()["legal_entitlement_established"] is False


def test_duplicate_finding_is_rejected_even_if_record_hash_is_identical(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "duplicate.sqlite3")
    record = _record(store, tenant="alpha", finding="finding-a", documented="100", supported="80", claimed="60", approved="50", settled="40")
    with pytest.raises(RecoveryPortfolioError, match="double count"):
        rollup_recovery_portfolio(tenant_id="alpha", records=(record, record))


def test_cross_tenant_and_cross_currency_rollups_fail_closed(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "boundaries.sqlite3")
    alpha = _record(store, tenant="alpha", finding="finding-a", documented="100", supported="80", claimed="60", approved="50", settled="40")
    beta = _record(store, tenant="beta", finding="finding-b", documented="100", supported="80", claimed="60", approved="50", settled="40")
    usd = _record(store, tenant="alpha", finding="finding-c", documented="100", supported="80", claimed="60", approved="50", settled="40", currency="USD")
    with pytest.raises(RecoveryPortfolioError, match="cross-tenant"):
        rollup_recovery_portfolio(tenant_id="alpha", records=(alpha, beta))
    with pytest.raises(RecoveryPortfolioError, match="cross-currency"):
        rollup_recovery_portfolio(tenant_id="alpha", records=(alpha, usd))


def test_portfolio_hash_is_order_independent_but_economic_state_sensitive(tmp_path):
    store = RecoveryReconciliationStore(tmp_path / "hash.sqlite3")
    first = _record(store, tenant="alpha", finding="finding-a", documented="100", supported="80", claimed="60", approved="50", settled="40")
    second = _record(store, tenant="alpha", finding="finding-b", documented="200", supported="150", claimed="120", approved="100", settled="70")
    left = rollup_recovery_portfolio(tenant_id="alpha", records=(first, second))
    right = rollup_recovery_portfolio(tenant_id="alpha", records=(second, first))
    changed = _record(store, tenant="alpha", finding="finding-c", documented="300", supported="230", claimed="181", approved="150", settled="110")
    assert left.portfolio_hash == right.portfolio_hash
    assert left.portfolio_hash != rollup_recovery_portfolio(tenant_id="alpha", records=(first, changed)).portfolio_hash
