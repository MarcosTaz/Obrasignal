from factory_cloud.assurance_backup import create_backup, restore_backup
from factory_cloud.assurance_ops import AssuranceOperations
from factory_cloud.assurance_store import AssuranceStore
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _build_case(service: IndustrialClaimsService, *, tenant_id: str, event_ref: str):
    result = service.analyze(
        tenant_id=tenant_id,
        actor_id=f"{tenant_id}-analyst",
        customer_ref=f"{tenant_id}-oem",
        program_ref=f"{tenant_id}-program",
        event_ref=event_ref,
        claim_family="TOOLING",
        commercial_basis_ref=f"{tenant_id}-po",
        cost_evidence_ref=f"{tenant_id}-invoice",
        currency="EUR",
        commercial_basis_content=f"signed tooling terms for {tenant_id}",
        event_evidence_content=f"documented cancellation event for {tenant_id}",
        cost_evidence_content=f"invoice and ledger supporting tooling exposure for {tenant_id}",
        gross_cost="50000",
        prior_payment="10000",
        notice_deadline_not_applicable=True,
    )
    service.review(
        tenant_id=tenant_id,
        finding_id=result.finding.finding_id,
        reviewer=f"{tenant_id}-reviewer",
        approved=True,
        reason="documented candidate accepted for internal workflow",
    )
    service.action(tenant_id=tenant_id, finding_id=result.finding.finding_id, actor_id=f"{tenant_id}-operator")
    service.resolve(
        tenant_id=tenant_id,
        finding_id=result.finding.finding_id,
        outcome_id="payment-1",
        recovered_amount="35000",
        currency="EUR",
        evidence_ref=f"{tenant_id}-bank-1",
        evidence_content=f"documented bank statement for 35000 EUR for {tenant_id}",
        actor_id=f"{tenant_id}-operator",
    )
    return result


def test_backup_restore_preserves_complete_tenant_scoped_dossier(tmp_path):
    live = tmp_path / "industrial.sqlite3"
    service = IndustrialClaimsService(live)
    alpha = _build_case(service, tenant_id="alpha", event_ref="cancel-alpha")
    beta = _build_case(service, tenant_id="beta", event_ref="cancel-beta")

    backup = tmp_path / "backup.sqlite3"
    record = create_backup(live, backup)
    assert record.integrity == "ok"
    assert record.sha256
    live.unlink()
    restored = restore_backup(backup, live)
    assert restored.integrity == "ok"

    store = AssuranceStore(live)
    ops = AssuranceOperations(store)
    restored_service = IndustrialClaimsService(live)
    read_model = IndustrialClaimsReadModel(live)

    assert store.count("evidence", "alpha") == 4
    assert store.count("evidence", "beta") == 4
    assert store.count("findings", "alpha") == 1
    assert store.count("findings", "beta") == 1
    assert store.count("audit_events", "alpha") == 4
    assert store.count("audit_events", "beta") == 4
    assert restored_service.case_store.count("alpha") == 1
    assert restored_service.case_store.count("beta") == 1
    assert restored_service.index.count_entitlements("alpha") == 1
    assert restored_service.index.count_entitlements("beta") == 1
    assert restored_service.index.count_fingerprints("alpha") == 1
    assert restored_service.index.count_fingerprints("beta") == 1

    assert ops.get_state(tenant_id="alpha", finding_id=alpha.finding.finding_id) == "RECOVERED"
    alpha_outcomes = ops.outcomes(tenant_id="alpha")
    beta_outcomes = ops.outcomes(tenant_id="beta")
    assert len(alpha_outcomes) == 1
    assert len(beta_outcomes) == 1
    assert alpha_outcomes[0].outcome_id != beta_outcomes[0].outcome_id
    assert alpha_outcomes[0].recovered_amount == "35000"
    assert alpha_outcomes[0].currency == "EUR"
    assert alpha_outcomes[0].evidence_ref.endswith(":outcome-evidence")

    alpha_detail = read_model.get_finding(tenant_id="alpha", finding_id=alpha.finding.finding_id)
    beta_detail = read_model.get_finding(tenant_id="beta", finding_id=beta.finding.finding_id)
    assert alpha_detail["case"]["customer_ref"] == "alpha-oem"
    assert beta_detail["case"]["customer_ref"] == "beta-oem"
    assert alpha_detail["case"]["recovery_fingerprint"] != beta_detail["case"]["recovery_fingerprint"]
    assert alpha_detail["entitlement"]["recoverability_established"] is False
    assert alpha_detail["raw_document_content_included"] is False
    serialized = repr(alpha_detail)
    assert "signed tooling terms" not in serialized
    assert "documented cancellation event" not in serialized
    assert "invoice and ledger" not in serialized
    assert "documented bank statement" not in serialized
