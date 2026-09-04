import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.dossier import AssistedRecoveryAssessment
from vertical_apps.industrial_claims.recovery_reconciliation_store import RecoveryReconciliationStoreError
from vertical_apps.industrial_claims.recovery_workflow import SupplierRecoveryWorkflow
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _assessment():
    return AssistedRecoveryAssessment(
        reviewer="reviewer-2",
        contract_change_truth="Reviewed customer change and commercial basis.",
        event_chronology="Customer change preceded incremental engineering work.",
        causation_state="SUPPORTED",
        causation_summary="Documentary chronology supports the change-to-cost sequence.",
        customer_responsibility_state="SUPPORTED",
        customer_responsibility_summary="Commercial basis supports internal recovery review without legal conclusion.",
        prior_recovery_state="VERIFIED_PARTIAL",
        prior_recovery_summary="Prior credits and payments were reconciled against the ledger.",
        confidence="HIGH",
        next_action="Independent review of the remaining supported-unclaimed and approved-unsettled positions.",
    )


def _case(service):
    return service.analyze(
        tenant_id="alpha",
        actor_id="analyst-1",
        customer_ref="oem",
        program_ref="program-a",
        event_ref="ecn-10",
        claim_family="NRE",
        commercial_basis_ref="po-change-10",
        cost_evidence_ref="ledger-10",
        gross_cost="120000",
        currency="EUR",
        commercial_basis_content="bounded commercial basis",
        event_evidence_content="customer engineering change",
        cost_evidence_content="incremental cost ledger",
        notice_deadline_not_applicable=True,
    )


def test_current_case_reconciliation_is_persisted_and_rendered_into_supplier_recovery_dossier(tmp_path):
    service = IndustrialClaimsService(tmp_path / "workflow.sqlite3")
    result = _case(service)
    workflow = SupplierRecoveryWorkflow(service)
    record = workflow.record_reconciliation(
        tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="reviewer-2",
        evidence_ref="reconciliation-pack-v1", documented_cost="120000", mitigation="20000",
        evidence_supported="80000", claimed="65000", approved="50000", settled="30000", currency="EUR",
    )
    dossier = workflow.build_latest_dossier(tenant_id="alpha", finding_id=result.finding.finding_id, assessment=_assessment())
    markdown = workflow.render_latest_dossier_markdown(tenant_id="alpha", finding_id=result.finding.finding_id, assessment=_assessment())
    assert record.sequence == 1
    assert dossier["deliverable"] == "SUPPLIER_RECOVERY_DOSSIER"
    assert dossier["recovery_reconciliation_persistence"]["append_only_history"] is True
    assert dossier["recovery_reconciliation_persistence"]["reconciliation_hash"] == record.reconciliation_hash
    assert dossier["recovery_reconciliation"]["supported_unclaimed"] == "15000"
    assert markdown.startswith("# Supplier Recovery — Recovery Dossier")
    assert "## Recovery reconciliation" in markdown


def test_superseded_finding_cannot_receive_or_render_new_reconciliation(tmp_path):
    service = IndustrialClaimsService(tmp_path / "revision-workflow.sqlite3")
    first = _case(service)
    workflow = SupplierRecoveryWorkflow(service)
    workflow.record_reconciliation(
        tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="reviewer-2",
        evidence_ref="reconciliation-pack-v1", documented_cost="120000", mitigation="20000",
        evidence_supported="80000", claimed="65000", approved="50000", settled="30000", currency="EUR",
    )
    amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-3",
        customer_ref="oem", program_ref="program-a", event_ref="ecn-10", claim_family="NRE",
        commercial_basis_ref="po-change-10", cost_evidence_ref="ledger-10-v2", gross_cost="125000", currency="EUR",
        commercial_basis_content="bounded commercial basis", event_evidence_content="customer engineering change",
        cost_evidence_content="corrected incremental cost ledger", notice_deadline_not_applicable=True,
    )
    with pytest.raises(AssuranceStoreError, match="superseded"):
        workflow.record_reconciliation(
            tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="reviewer-3", evidence_ref="stale-pack",
            documented_cost="120000", mitigation="20000", evidence_supported="80000", claimed="65000",
            approved="50000", settled="30000", currency="EUR",
        )
    with pytest.raises(AssuranceStoreError, match="superseded"):
        workflow.build_latest_dossier(tenant_id="alpha", finding_id=first.finding.finding_id, assessment=_assessment())


def test_reconciliation_regression_requires_documented_reason(tmp_path):
    service = IndustrialClaimsService(tmp_path / "reversal-workflow.sqlite3")
    result = _case(service)
    workflow = SupplierRecoveryWorkflow(service)
    workflow.record_reconciliation(
        tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="reviewer-2", evidence_ref="settlement-v1",
        documented_cost="120000", mitigation="20000", evidence_supported="80000", claimed="70000",
        approved="60000", settled="50000", currency="EUR",
    )
    with pytest.raises(RecoveryReconciliationStoreError, match="reversal_reason"):
        workflow.record_reconciliation(
            tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="reviewer-3", evidence_ref="credit-note-v2",
            documented_cost="120000", mitigation="20000", evidence_supported="80000", claimed="65000",
            approved="55000", settled="45000", currency="EUR",
        )
    corrected = workflow.record_reconciliation(
        tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="reviewer-3", evidence_ref="credit-note-v2",
        documented_cost="120000", mitigation="20000", evidence_supported="80000", claimed="65000",
        approved="55000", settled="45000", currency="EUR",
        reversal_reason="Customer credit-note correction reduced the accepted settlement; source retained.",
    )
    assert corrected.sequence == 2
