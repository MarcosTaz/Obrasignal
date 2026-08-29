from factory_cloud.assurance_backup import create_backup, restore_backup
from factory_cloud.assurance_ops import AssuranceOperations
from factory_cloud.assurance_store import AssuranceStore
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def test_backup_restore_preserves_claim_and_verified_outcome(tmp_path):
    live = tmp_path / "industrial.sqlite3"
    service = IndustrialClaimsService(live)
    result = service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        claim_family="TOOLING",
        commercial_basis_ref="po-1",
        cost_evidence_ref="invoice-1",
        gross_cost="50000",
        prior_payment="10000",
    )
    service.review(tenant_id="alpha", finding_id=result.finding.finding_id, reviewer="reviewer", approved=True, reason="supported")
    service.action(tenant_id="alpha", finding_id=result.finding.finding_id)
    service.resolve(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        outcome_id="alpha:payment-1",
        recovered_amount="35000",
        currency="EUR",
        evidence_ref="bank-1",
    )

    backup = tmp_path / "backup.sqlite3"
    record = create_backup(live, backup)
    assert record.integrity == "ok"
    assert record.sha256

    live.unlink()
    restored = restore_backup(backup, live)
    assert restored.integrity == "ok"

    store = AssuranceStore(live)
    ops = AssuranceOperations(store)
    assert store.count("evidence", "alpha") == 3
    assert store.count("findings", "alpha") == 1
    assert ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "RECOVERED"
    outcomes = ops.outcomes(tenant_id="alpha")
    assert len(outcomes) == 1
    assert outcomes[0].recovered_amount == "35000"
