import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _payload(**overrides):
    payload = dict(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="case-metadata-event",
        claim_family="TOOLING",
        commercial_basis_ref="basis-1",
        cost_evidence_ref="cost-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger supporting tooling exposure",
        notice_deadline_not_applicable=True,
    )
    payload.update(overrides)
    return payload


def test_case_metadata_is_committed_with_shared_case_rows(tmp_path):
    service = IndustrialClaimsService(tmp_path / "case-metadata.sqlite3")

    result = service.analyze(**_payload())
    metadata = service.case_store.get(tenant_id="alpha", finding_id=result.finding.finding_id)

    assert service.case_store.count("alpha") == 1
    assert metadata.customer_ref == "oem-1"
    assert metadata.program_ref == "program-1"
    assert metadata.event_ref == "case-metadata-event"
    assert metadata.entitlement_id == result.entitlement.entitlement_id
    assert metadata.deadline_id == result.deadline.deadline_id
    assert metadata.recovery_fingerprint == result.fingerprint.fingerprint
    assert metadata.notice_deadline_state == "DECLARED_NONE_FOR_REVIEW"


def test_case_metadata_failure_rolls_back_new_fingerprint_and_all_new_case_rows(tmp_path, monkeypatch):
    service = IndustrialClaimsService(tmp_path / "case-metadata-rollback.sqlite3")

    original_put = service.case_store.put

    def fail_case_metadata(_item, *, connection=None):
        raise RuntimeError("injected case metadata persistence failure")

    monkeypatch.setattr(service.case_store, "put", fail_case_metadata)
    with pytest.raises(RuntimeError, match="injected case metadata persistence failure"):
        service.analyze(**_payload())

    assert service.index.count_entitlements("alpha") == 0
    assert service.index.count_fingerprints("alpha") == 0
    assert service.case_store.count("alpha") == 0
    assert service.store.count("evidence", "alpha") == 0
    assert service.store.count("calculations", "alpha") == 0
    assert service.store.count("findings", "alpha") == 0

    monkeypatch.setattr(service.case_store, "put", original_put)
    result = service.analyze(**_payload())
    assert result.is_new_recovery is True
    assert service.index.count_fingerprints("alpha") == 1
    assert service.case_store.count("alpha") == 1


def test_immutable_case_metadata_collision_rolls_back_alternate_fingerprint(tmp_path):
    service = IndustrialClaimsService(tmp_path / "case-metadata-collision.sqlite3")
    first = service.analyze(**_payload())

    with pytest.raises(AssuranceStoreError, match="immutable industrial case metadata collision"):
        service.analyze(**_payload(customer_ref="oem-2"))

    assert service.index.count_entitlements("alpha") == 1
    assert service.index.count_fingerprints("alpha") == 1
    assert service.case_store.count("alpha") == 1
    persisted = service.case_store.get(tenant_id="alpha", finding_id=first.finding.finding_id)
    assert persisted.customer_ref == "oem-1"
    assert persisted.notice_deadline_state == "DECLARED_NONE_FOR_REVIEW"
    assert service.store.count("findings", "alpha") == 1
