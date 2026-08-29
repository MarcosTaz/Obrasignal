import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.case_store import IndustrialCaseMetadata
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


def test_distinct_contracts_can_share_event_reference_without_case_id_collision(tmp_path):
    service = IndustrialClaimsService(tmp_path / "case-metadata-distinct-contracts.sqlite3")
    first = service.analyze(**_payload())
    second = service.analyze(**_payload(
        customer_ref="oem-2",
        program_ref="program-2",
        commercial_basis_ref="basis-2",
        cost_evidence_ref="cost-2",
        commercial_basis_content="signed tooling agreement for second contract",
        cost_evidence_content="cost ledger supporting second tooling exposure",
    ))

    assert first.is_new_recovery is True
    assert second.is_new_recovery is True
    assert first.fingerprint.fingerprint != second.fingerprint.fingerprint
    assert first.finding.finding_id != second.finding.finding_id
    assert first.entitlement.entitlement_id != second.entitlement.entitlement_id
    assert first.calculation.calculation_id != second.calculation.calculation_id
    assert first.deadline.deadline_id != second.deadline.deadline_id
    assert service.index.count_entitlements("alpha") == 2
    assert service.index.count_fingerprints("alpha") == 2
    assert service.case_store.count("alpha") == 2
    assert service.store.count("findings", "alpha") == 2

    first_metadata = service.case_store.get(tenant_id="alpha", finding_id=first.finding.finding_id)
    second_metadata = service.case_store.get(tenant_id="alpha", finding_id=second.finding.finding_id)
    assert first_metadata.event_ref == second_metadata.event_ref == "case-metadata-event"
    assert first_metadata.customer_ref == "oem-1"
    assert second_metadata.customer_ref == "oem-2"


def test_case_store_rejects_tenant_outside_verified_provider_contract(tmp_path):
    service = IndustrialClaimsService(tmp_path / "case-metadata-tenant.sqlite3")
    result = service.analyze(**_payload())
    persisted = service.case_store.get(tenant_id="alpha", finding_id=result.finding.finding_id)
    malformed = IndustrialCaseMetadata(
        finding_id=persisted.finding_id,
        tenant_id="invalid tenant",
        claim_family=persisted.claim_family,
        customer_ref=persisted.customer_ref,
        program_ref=persisted.program_ref,
        event_ref=persisted.event_ref,
        entitlement_id=persisted.entitlement_id,
        deadline_id=persisted.deadline_id,
        recovery_fingerprint=persisted.recovery_fingerprint,
        notice_deadline_state=persisted.notice_deadline_state,
        missing_evidence=persisted.missing_evidence,
    )

    with pytest.raises(AssuranceStoreError, match="tenant_id is invalid"):
        service.case_store.put(malformed)
    with pytest.raises(AssuranceStoreError, match="tenant_id is invalid"):
        service.case_store.count("invalid tenant")

    assert service.case_store.count("alpha") == 1


def test_case_store_still_rejects_same_internal_id_with_different_metadata(tmp_path):
    service = IndustrialClaimsService(tmp_path / "case-metadata-immutable.sqlite3")
    result = service.analyze(**_payload())
    persisted = service.case_store.get(tenant_id="alpha", finding_id=result.finding.finding_id)
    conflicting = IndustrialCaseMetadata(
        finding_id=persisted.finding_id,
        tenant_id=persisted.tenant_id,
        claim_family=persisted.claim_family,
        customer_ref="different-customer",
        program_ref=persisted.program_ref,
        event_ref=persisted.event_ref,
        entitlement_id=persisted.entitlement_id,
        deadline_id=persisted.deadline_id,
        recovery_fingerprint=persisted.recovery_fingerprint,
        notice_deadline_state=persisted.notice_deadline_state,
        missing_evidence=persisted.missing_evidence,
    )

    with pytest.raises(AssuranceStoreError, match="immutable industrial case metadata collision"):
        service.case_store.put(conflicting)

    unchanged = service.case_store.get(tenant_id="alpha", finding_id=result.finding.finding_id)
    assert unchanged.customer_ref == "oem-1"
    assert service.case_store.count("alpha") == 1
