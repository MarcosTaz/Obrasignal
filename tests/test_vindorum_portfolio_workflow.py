import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.recovery_portfolio import RecoveryPortfolioError
from vertical_apps.industrial_claims.recovery_portfolio_workflow import VindorumPortfolioWorkflow
from vertical_apps.industrial_claims.recovery_reconciliation_store import RecoveryReconciliationStoreError
from vertical_apps.industrial_claims.recovery_workflow import VindorumWorkflow
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(service, *, event_ref, gross_cost="100", currency="EUR"):
    return service.analyze(
        tenant_id="alpha",
        actor_id=f"analyst-{event_ref}",
        customer_ref="oem",
        program_ref="program-a",
        event_ref=event_ref,
        claim_family="NRE",
        commercial_basis_ref=f"po-{event_ref}",
        cost_evidence_ref=f"ledger-{event_ref}",
        gross_cost=gross_cost,
        currency=currency,
        commercial_basis_content="bounded commercial basis",
        event_evidence_content=f"customer change {event_ref}",
        cost_evidence_content=f"cost ledger {event_ref}",
        notice_deadline_not_applicable=True,
    )


def _record(workflow, result, *, documented, supported, claimed, approved, settled, currency="EUR", evidence="pack"):
    return workflow.record_reconciliation(
        tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="portfolio-reviewer",
        evidence_ref=f"{evidence}-{result.finding.finding_id}", documented_cost=documented, mitigation="0",
        evidence_supported=supported, claimed=claimed, approved=approved, settled=settled, currency=currency,
    )


def test_portfolio_workflow_uses_latest_verified_reconciliation_for_each_current_case(tmp_path):
    service = IndustrialClaimsService(tmp_path / "portfolio-workflow.sqlite3")
    first = _case(service, event_ref="ecn-1")
    second = _case(service, event_ref="ecn-2", gross_cost="200")
    case_workflow = VindorumWorkflow(service)
    _record(case_workflow, first, documented="100", supported="80", claimed="60", approved="50", settled="40", evidence="v1")
    latest_first = _record(case_workflow, first, documented="100", supported="90", claimed="70", approved="60", settled="50", evidence="v2")
    latest_second = _record(case_workflow, second, documented="200", supported="150", claimed="120", approved="100", settled="70", evidence="v1")
    portfolio = VindorumPortfolioWorkflow(service).build_current_portfolio(
        tenant_id="alpha", finding_ids=(first.finding.finding_id, second.finding.finding_id)
    )
    assert portfolio.rollup.case_count == 2
    assert portfolio.rollup.amounts["evidence_supported"] == 240
    assert portfolio.rollup.amounts["settled"] == 120
    assert [item.reconciliation_sequence for item in portfolio.cases] == [2, 1]
    assert portfolio.cases[0].reconciliation_hash == latest_first.reconciliation_hash
    assert portfolio.cases[1].reconciliation_hash == latest_second.reconciliation_hash
    assert portfolio.as_dict()["current_revision_only"] is True
    assert portfolio.as_dict()["latest_reconciliation_only"] is True


def test_superseded_finding_is_excluded_fail_closed(tmp_path):
    service = IndustrialClaimsService(tmp_path / "superseded-portfolio.sqlite3")
    first = _case(service, event_ref="ecn-1")
    case_workflow = VindorumWorkflow(service)
    _record(case_workflow, first, documented="100", supported="80", claimed="60", approved="50", settled="40")
    amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-amend",
        customer_ref="oem", program_ref="program-a", event_ref="ecn-1", claim_family="NRE",
        commercial_basis_ref="po-ecn-1", cost_evidence_ref="ledger-ecn-1-v2", gross_cost="110", currency="EUR",
        commercial_basis_content="bounded commercial basis", event_evidence_content="customer change ecn-1",
        cost_evidence_content="corrected cost ledger", notice_deadline_not_applicable=True,
    )
    with pytest.raises(AssuranceStoreError, match="superseded"):
        VindorumPortfolioWorkflow(service).build_current_portfolio(
            tenant_id="alpha", finding_ids=(first.finding.finding_id,)
        )


def test_current_case_without_reconciliation_is_not_silently_zeroed(tmp_path):
    service = IndustrialClaimsService(tmp_path / "missing-reconciliation.sqlite3")
    result = _case(service, event_ref="ecn-3")
    with pytest.raises(RecoveryReconciliationStoreError, match="no persisted recovery reconciliation"):
        VindorumPortfolioWorkflow(service).build_current_portfolio(
            tenant_id="alpha", finding_ids=(result.finding.finding_id,)
        )


def test_portfolio_workflow_rejects_duplicate_ids_before_aggregation(tmp_path):
    service = IndustrialClaimsService(tmp_path / "duplicate-portfolio.sqlite3")
    result = _case(service, event_ref="ecn-4")
    case_workflow = VindorumWorkflow(service)
    _record(case_workflow, result, documented="100", supported="80", claimed="60", approved="50", settled="40")
    with pytest.raises(RecoveryPortfolioError, match="double count"):
        VindorumPortfolioWorkflow(service).build_current_portfolio(
            tenant_id="alpha", finding_ids=(result.finding.finding_id, result.finding.finding_id)
        )
