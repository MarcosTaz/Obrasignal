from vertical_apps.industrial_claims.dossier import AssistedRecoveryAssessment
from vertical_apps.industrial_claims.leakage_reconciliation import reconcile_recovery_ledger
from vertical_apps.industrial_claims.recovery_dossier import (
    CERTACTUM_DOSSIER,
    build_certactum_recovery_dossier,
    render_certactum_recovery_dossier_markdown,
)
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _assessment():
    return AssistedRecoveryAssessment(
        reviewer="reviewer-2",
        contract_change_truth="Customer change and bounded commercial basis reviewed.",
        event_chronology="Customer change preceded the documented incremental work.",
        causation_state="SUPPORTED",
        causation_summary="Documentary chronology supports the change-to-cost sequence.",
        customer_responsibility_state="SUPPORTED",
        customer_responsibility_summary="Commercial responsibility is supported for internal review; no legal conclusion is asserted.",
        prior_recovery_state="VERIFIED_PARTIAL",
        prior_recovery_summary="A partial prior recovery was reconciled against the reviewed ledger.",
        confidence="HIGH",
        next_action="Independent commercial review of the supported-unclaimed and approved-unsettled gaps.",
    )


def test_certactum_dossier_carries_reconciliation_without_promoting_gap_to_debt(tmp_path):
    service = IndustrialClaimsService(tmp_path / "certactum-dossier.sqlite3")
    result = service.analyze(
        tenant_id="alpha",
        actor_id="analyst-1",
        customer_ref="oem",
        program_ref="program-a",
        event_ref="ecn-7",
        claim_family="NRE",
        commercial_basis_ref="po-change-7",
        cost_evidence_ref="ledger-7",
        gross_cost="120000",
        currency="EUR",
        commercial_basis_content="bounded reimbursement basis",
        event_evidence_content="customer-issued engineering change",
        cost_evidence_content="incremental engineering cost ledger",
        notice_deadline_not_applicable=True,
    )
    reconciliation = reconcile_recovery_ledger(
        documented_cost="120000",
        mitigation="20000",
        evidence_supported="80000",
        claimed="65000",
        approved="50000",
        settled="30000",
        currency="EUR",
    )

    dossier = build_certactum_recovery_dossier(
        service,
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        assessment=_assessment(),
        reconciliation=reconciliation,
    )

    assert dossier["deliverable"] == CERTACTUM_DOSSIER
    assert dossier["identity"]["company"] == "Certactum"
    assert dossier["identity"]["legacy_name_customer_facing"] is False
    assert dossier["recovery_reconciliation"]["supported_unclaimed"] == "15000"
    assert dossier["recovery_reconciliation"]["approved_unsettled"] == "20000"
    assert dossier["recovery_reconciliation"]["legal_entitlement_established"] is False
    assert dossier["recovery_reconciliation"]["economic_gap_is_automatically_money_owed"] is False

    markdown = render_certactum_recovery_dossier_markdown(dossier)
    assert markdown.startswith("# Certactum — Supplier Recovery Dossier")
    assert "# CausLedger" not in markdown
    assert "## Recovery reconciliation" in markdown
    assert "Supported but unclaimed: 15000 EUR" in markdown
    assert "Approved but unsettled: 20000 EUR" in markdown
    assert "Economic gap automatically establishes money owed: False" in markdown
    assert "Legal entitlement established by reconciliation: False" in markdown
    assert "bounded reimbursement basis" not in markdown
    assert "customer-issued engineering change" not in markdown
    assert "incremental engineering cost ledger" not in markdown
