from datetime import date

import pytest

from factory_cloud.assurance_backup import create_backup, restore_backup
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.package import build_claim_package
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def test_corrected_recovery_journey_remains_single_auditable_recovery_end_to_end(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    service = IndustrialClaimsService(database)
    first = service.analyze(
        tenant_id="alpha", actor_id="analyst-1", customer_ref="oem-1", program_ref="launch-1",
        event_ref="cancel-1", claim_family="TOOLING", commercial_basis_ref="po-1", cost_evidence_ref="ledger-v1",
        gross_cost="100000", resale_reuse="25000", currency="EUR",
        commercial_basis_content="signed tooling purchase order and cancellation terms",
        event_evidence_content="documented customer cancellation",
        cost_evidence_content="initial tooling ledger supporting 100000 EUR gross exposure",
        notice_deadline_not_applicable=True,
    )
    labels = {
        "customer_ref": "oem-1",
        "program_ref": "launch-1",
        "event_ref": "cancel-1",
        "as_of_date": date(2026, 8, 30),
    }
    first_package = build_claim_package(service, first, **labels)
    assert first_package["revision"]["number"] == 1
    assert first_package["net_potential"] == "75000"

    second = amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-2",
        customer_ref="oem-1", program_ref="launch-1", event_ref="cancel-1", claim_family="TOOLING",
        commercial_basis_ref="po-1", cost_evidence_ref="ledger-v2", gross_cost="105000", resale_reuse="25000",
        prior_payment="5000", currency="EUR",
        commercial_basis_content="signed tooling purchase order and cancellation terms",
        event_evidence_content="documented customer cancellation plus corrected quantity correspondence",
        cost_evidence_content="corrected tooling ledger supporting 105000 EUR gross exposure",
        notice_deadline_not_applicable=True,
    )
    assert service.index.count_fingerprints("alpha") == 1
    assert service.revision_store.count("alpha") == 2
    assert second.calculation.output_value == "75000"

    with pytest.raises(ValueError, match="current non-superseded"):
        build_claim_package(service, first, **labels)
    second_package = build_claim_package(service, second, **labels)
    assert second_package["revision"]["number"] == 2
    assert second_package["revision"]["supersedes_finding_id"] == first.finding.finding_id

    first_detail = service.read_model.get_finding(tenant_id="alpha", finding_id=first.finding.finding_id)
    assert first_detail["revision"]["is_current"] is False
    assert first_detail["revision"]["current_finding_id"] == second.finding.finding_id

    service.review(
        tenant_id="alpha", finding_id=second.finding.finding_id, reviewer="reviewer-1",
        approved=True, reason="corrected evidence and economics independently reviewed",
    )
    with pytest.raises(ValueError, match="lifecycle state is stale"):
        build_claim_package(service, second, **labels)
    assert service.action(tenant_id="alpha", finding_id=second.finding.finding_id, actor_id="operator-1") == "ACTIONED"
    outcome = service.resolve(
        tenant_id="alpha", finding_id=second.finding.finding_id, outcome_id="settlement-final",
        recovered_amount="70000", currency="EUR", evidence_ref="bank-settlement-1",
        evidence_content="bank and signed settlement evidence proving final cumulative 70000 EUR outcome",
        actor_id="operator-1",
    )
    assert outcome.state == "RECOVERED"

    final_detail = service.read_model.get_finding(tenant_id="alpha", finding_id=second.finding.finding_id)
    assert final_detail["finding"]["state"] == "RECOVERED"
    assert final_detail["revision"]["is_current"] is True
    assert final_detail["revision"]["number"] == 2
    assert len(final_detail["outcomes"]) == 1
    assert final_detail["outcomes"][0]["recovered_amount"] == "70000"
    assert final_detail["raw_document_content_included"] is False

    backup = tmp_path / "backup.sqlite3"
    assert create_backup(database, backup).integrity == "ok"
    database.unlink()
    assert restore_backup(backup, database).integrity == "ok"
    restored = IndustrialClaimsService(database)
    restored_final = restored.read_model.get_finding(tenant_id="alpha", finding_id=second.finding.finding_id)
    restored_old = restored.read_model.get_finding(tenant_id="alpha", finding_id=first.finding.finding_id)
    assert restored_final["finding"]["state"] == "RECOVERED"
    assert restored_final["revision"]["current_finding_id"] == second.finding.finding_id
    assert restored_old["revision"]["superseded_by_finding_id"] == second.finding.finding_id
    assert restored.index.count_fingerprints("alpha") == 1
    assert restored.revision_store.count("alpha") == 2
