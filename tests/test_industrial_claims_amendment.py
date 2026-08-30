import pytest

from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.amendment import amend_case
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


def _amend(service: IndustrialClaimsService, finding_id: str, **overrides):
    payload = dict(
        tenant_id="alpha",
        finding_id=finding_id,
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
        event_evidence_content="documented cancellation event with corrected supporting correspondence",
        cost_evidence_content="corrected cost ledger supporting 12000 EUR exposure",
        notice_deadline_not_applicable=True,
    )
    payload.update(overrides)
    return amend_case(service, **payload)


def test_amendment_preserves_fingerprint_creates_revision_two_and_resets_review(tmp_path):
    service = IndustrialClaimsService(tmp_path / "amend.sqlite3")
    first = _initial(service)
    service.review(
        tenant_id="alpha",
        finding_id=first.finding.finding_id,
        reviewer="reviewer-1",
        approved=True,
        reason="initial reconstruction reviewed",
    )

    second = _amend(service, first.finding.finding_id)

    assert second.is_new_recovery is False
    assert second.fingerprint.fingerprint == first.fingerprint.fingerprint
    assert second.finding.finding_id != first.finding.finding_id
    assert ":r2:finding" in second.finding.finding_id
    assert second.finding.state == "READY_FOR_REVIEW"
    assert second.finding.reviewer is None
    assert second.calculation.output_value == "12000"
    assert service.index.count_fingerprints("alpha") == 1
    assert service.revision_store.count("alpha") == 2
    old_revision = service.revision_store.get(tenant_id="alpha", finding_id=first.finding.finding_id)
    new_revision = service.revision_store.require_current(tenant_id="alpha", finding_id=second.finding.finding_id)
    assert old_revision.is_current is False
    assert new_revision.revision == 2
    assert new_revision.supersedes_finding_id == first.finding.finding_id

    with pytest.raises(AssuranceStoreError, match="superseded"):
        service.action(tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="operator")

    service.review(
        tenant_id="alpha",
        finding_id=second.finding.finding_id,
        reviewer="reviewer-2",
        approved=True,
        reason="corrected revision independently reviewed",
    )
    assert service.action(tenant_id="alpha", finding_id=second.finding.finding_id, actor_id="operator") == "ACTIONED"


def test_amendment_cannot_change_fingerprint_identity_fields(tmp_path):
    service = IndustrialClaimsService(tmp_path / "identity.sqlite3")
    first = _initial(service)

    changes = (
        {"customer_ref": "other-oem"},
        {"program_ref": "other-program"},
        {"event_ref": "other-event"},
        {"claim_family": "WIP"},
        {"commercial_basis_ref": "other-basis"},
    )
    for change in changes:
        with pytest.raises(AssuranceOperationError, match="cannot change recovery fingerprint identity fields"):
            _amend(service, first.finding.finding_id, **change)

    assert service.revision_store.count("alpha") == 1
    assert service.store.count("findings", "alpha") == 1
    assert service.index.count_fingerprints("alpha") == 1


def test_amendment_is_blocked_after_action_and_final_outcome(tmp_path):
    action_db = tmp_path / "after-action.sqlite3"
    service = IndustrialClaimsService(action_db)
    first = _initial(service)
    service.review(tenant_id="alpha", finding_id=first.finding.finding_id, reviewer="reviewer", approved=True, reason="reviewed")
    service.action(tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="operator")

    with pytest.raises(AssuranceOperationError, match="only unresolved, review-ready, approved or rejected findings may be amended"):
        _amend(service, first.finding.finding_id)
    assert service.revision_store.count("alpha") == 1
    assert service.store.count("findings", "alpha") == 1

    service.resolve(
        tenant_id="alpha", finding_id=first.finding.finding_id, outcome_id="settlement-1", recovered_amount="5000",
        currency="EUR", evidence_ref="bank-1", evidence_content="bank settlement evidence", actor_id="operator",
    )
    with pytest.raises(AssuranceOperationError, match="only unresolved, review-ready, approved or rejected findings may be amended"):
        _amend(service, first.finding.finding_id)


def test_amendment_failure_rolls_back_new_case_revision_and_evidence(tmp_path, monkeypatch):
    service = IndustrialClaimsService(tmp_path / "rollback.sqlite3")
    first = _initial(service)
    original_supersede = service.revision_store.supersede

    def fail_supersede(**_kwargs):
        raise RuntimeError("injected revision supersession failure")

    monkeypatch.setattr(service.revision_store, "supersede", fail_supersede)
    with pytest.raises(RuntimeError, match="injected revision supersession failure"):
        _amend(service, first.finding.finding_id)

    assert service.revision_store.count("alpha") == 1
    assert service.revision_store.require_current(tenant_id="alpha", finding_id=first.finding.finding_id).revision == 1
    assert service.store.count("findings", "alpha") == 1
    assert service.store.count("evidence", "alpha") == 3
    assert service.case_store.count("alpha") == 1
    assert service.index.count_fingerprints("alpha") == 1
    assert service.index.count_entitlements("alpha") == 1

    monkeypatch.setattr(service.revision_store, "supersede", original_supersede)
    second = _amend(service, first.finding.finding_id)
    assert second.finding.state == "READY_FOR_REVIEW"
    assert service.revision_store.count("alpha") == 2
    assert service.store.count("findings", "alpha") == 2
    assert service.store.count("evidence", "alpha") == 6
    assert service.case_store.count("alpha") == 2
    assert service.index.count_fingerprints("alpha") == 1
    assert service.index.count_entitlements("alpha") == 2


def test_regular_analyze_cannot_reactivate_superseded_revision(tmp_path):
    service = IndustrialClaimsService(tmp_path / "replay-after-amend.sqlite3")
    first = _initial(service)
    _amend(service, first.finding.finding_id)

    with pytest.raises(AssuranceStoreError, match="newer current revision"):
        _initial(service)
    assert service.revision_store.count("alpha") == 2
    assert service.store.count("findings", "alpha") == 2
