from factory_cloud.assurance_backup import create_backup, restore_backup
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _initial(service: IndustrialClaimsService):
    return service.analyze(
        tenant_id="alpha",
        actor_id="analyst-1",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        claim_family="TOOLING",
        commercial_basis_ref="basis-1",
        cost_evidence_ref="cost-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger supporting 10000 EUR exposure",
        notice_deadline_not_applicable=True,
    )


def test_backup_restore_preserves_revision_supersession_and_current_pointer(tmp_path):
    live = tmp_path / "industrial.sqlite3"
    service = IndustrialClaimsService(live)
    first = _initial(service)
    second = amend_case(
        service,
        tenant_id="alpha",
        finding_id=first.finding.finding_id,
        actor_id="analyst-2",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        claim_family="TOOLING",
        commercial_basis_ref="basis-1",
        cost_evidence_ref="cost-2",
        gross_cost="12000",
        currency="EUR",
        commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event with corrected correspondence",
        cost_evidence_content="corrected cost ledger supporting 12000 EUR exposure",
        notice_deadline_not_applicable=True,
    )

    backup = tmp_path / "backup.sqlite3"
    assert create_backup(live, backup).integrity == "ok"
    live.unlink()
    assert restore_backup(backup, live).integrity == "ok"

    restored = IndustrialClaimsService(live)
    read_model = IndustrialClaimsReadModel(live)
    assert restored.revision_store.count("alpha") == 2

    historical = restored.revision_store.get(tenant_id="alpha", finding_id=first.finding.finding_id)
    current = restored.revision_store.require_current(tenant_id="alpha", finding_id=second.finding.finding_id)
    assert historical.revision == 1
    assert historical.is_current is False
    assert current.revision == 2
    assert current.is_current is True
    assert current.supersedes_finding_id == first.finding.finding_id
    assert current.recovery_fingerprint == historical.recovery_fingerprint

    historical_detail = read_model.get_finding(tenant_id="alpha", finding_id=first.finding.finding_id)
    current_detail = read_model.get_finding(tenant_id="alpha", finding_id=second.finding.finding_id)
    assert historical_detail["revision"] == {
        "number": 1,
        "is_current": False,
        "supersedes_finding_id": None,
    }
    assert current_detail["revision"] == {
        "number": 2,
        "is_current": True,
        "supersedes_finding_id": first.finding.finding_id,
    }
    assert current_detail["raw_document_content_included"] is False

    queue = read_model.list_findings(tenant_id="alpha", states=("READY_FOR_REVIEW",), limit=100)
    assert [item.finding_id for item in queue] == [second.finding.finding_id]
