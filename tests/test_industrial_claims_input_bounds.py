import pytest

from auth_context import RequestIdentity
from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.service import (
    MAX_FINDING_ID_CHARS,
    MAX_MISSING_EVIDENCE_CHARS,
    MAX_MISSING_EVIDENCE_ITEMS,
    MAX_REASON_CHARS,
    MAX_REFERENCE_CHARS,
    MAX_TENANT_CHARS,
    IndustrialClaimsService,
)
from vertical_apps.industrial_claims.web import create_app


def _analyze(service: IndustrialClaimsService, **overrides):
    payload = dict(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="event-1",
        claim_family="TOOLING", commercial_basis_ref="basis-1", cost_evidence_ref="cost-1", gross_cost="10000",
        currency="EUR", commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event", cost_evidence_content="cost ledger supporting tooling exposure",
        notice_deadline_not_applicable=True,
    )
    payload.update(overrides)
    return service.analyze(**payload)


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(account_id=tenant_id, authenticated=True, subject=actor_id, claims={"sub": actor_id, "roles": list(roles)})


@pytest.mark.parametrize("tenant", ["t" * (MAX_TENANT_CHARS + 1), "alpha:evil", "alpha\nevil", "-alpha", "alpha/evil"])
def test_invalid_tenant_contract_fails_before_any_case_persistence(tmp_path, tenant):
    service = IndustrialClaimsService(tmp_path / "invalid-tenant.sqlite3")
    with pytest.raises(AssuranceKernelError, match="verified account-id contract"):
        _analyze(service, tenant_id=tenant)
    assert service.index.count_fingerprints("alpha") == 0
    assert service.case_store.count("alpha") == 0
    assert service.store.count("evidence", "alpha") == 0
    assert service.store.count("findings", "alpha") == 0


def test_oversized_case_reference_fails_before_any_case_persistence(tmp_path):
    service = IndustrialClaimsService(tmp_path / "oversized-ref.sqlite3")
    with pytest.raises(AssuranceKernelError, match="customer_ref exceeds"):
        _analyze(service, customer_ref="x" * (MAX_REFERENCE_CHARS + 1))
    assert service.index.count_fingerprints("alpha") == 0
    assert service.case_store.count("alpha") == 0
    assert service.store.count("evidence", "alpha") == 0
    assert service.store.count("findings", "alpha") == 0


def test_missing_evidence_collection_and_keys_are_bounded_before_persistence(tmp_path):
    service = IndustrialClaimsService(tmp_path / "missing-bounds.sqlite3")
    with pytest.raises(AssuranceKernelError, match="missing_evidence exceeds"):
        _analyze(service, missing_evidence=tuple(f"key-{i}" for i in range(MAX_MISSING_EVIDENCE_ITEMS + 1)))
    with pytest.raises(AssuranceKernelError, match="missing evidence key exceeds"):
        _analyze(service, event_ref="event-2", missing_evidence=("x" * (MAX_MISSING_EVIDENCE_CHARS + 1),))
    assert service.index.count_fingerprints("alpha") == 0
    assert service.case_store.count("alpha") == 0
    assert service.store.count("findings", "alpha") == 0


@pytest.mark.parametrize("value", ["1e999999", "1e-999999", "9" * 129, "0." + "1" * 19])
def test_pathological_decimal_shapes_fail_before_case_persistence(tmp_path, value):
    service = IndustrialClaimsService(tmp_path / "decimal-capacity.sqlite3")
    with pytest.raises(AssuranceKernelError, match="numeric input capacity"):
        _analyze(service, gross_cost=value)
    assert service.index.count_fingerprints("alpha") == 0
    assert service.case_store.count("alpha") == 0
    assert service.store.count("calculations", "alpha") == 0
    assert service.store.count("findings", "alpha") == 0


def test_large_but_bounded_decimal_shape_remains_exact(tmp_path):
    service = IndustrialClaimsService(tmp_path / "decimal-supported.sqlite3")
    gross = "9" * 36
    result = _analyze(service, gross_cost=gross, prior_payment="1")
    assert result.calculation.output_value == str(int(gross) - 1)
    assert result.finding.state == "READY_FOR_REVIEW"


def test_review_reason_is_bounded_without_mutating_finding_state(tmp_path):
    service = IndustrialClaimsService(tmp_path / "review-bounds.sqlite3")
    result = _analyze(service)
    with pytest.raises(AssuranceOperationError, match="review reason exceeds"):
        service.review(tenant_id="alpha", finding_id=result.finding.finding_id, reviewer="reviewer", approved=True, reason="r" * (MAX_REASON_CHARS + 1))
    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "READY_FOR_REVIEW"
    assert service.store.count("audit_events", "alpha") == 1


def test_oversized_resolution_identifiers_and_amounts_fail_before_outcome_evidence_persistence(tmp_path):
    service = IndustrialClaimsService(tmp_path / "resolution-bounds.sqlite3")
    result = _analyze(service)
    service.review(tenant_id="alpha", finding_id=result.finding.finding_id, reviewer="reviewer", approved=True, reason="reviewed")
    service.action(tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="operator")

    with pytest.raises(AssuranceOperationError, match="outcome_id exceeds"):
        service.resolve(tenant_id="alpha", finding_id=result.finding.finding_id, outcome_id="o" * (MAX_REFERENCE_CHARS + 1), recovered_amount="1000", currency="EUR", evidence_ref="bank-1", evidence_content="bank settlement evidence", actor_id="operator")
    with pytest.raises(AssuranceOperationError, match="numeric input capacity"):
        service.resolve(tenant_id="alpha", finding_id=result.finding.finding_id, outcome_id="outcome-2", recovered_amount="1e999999", currency="EUR", evidence_ref="bank-2", evidence_content="bank settlement evidence", actor_id="operator")

    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "ACTIONED"
    assert service.ops.outcomes(tenant_id="alpha") == ()
    assert service.store.count("evidence", "alpha") == 3


def test_finding_detail_path_is_bounded_before_database_lookup(tmp_path):
    client = create_app(tmp_path / "detail-bounds.sqlite3", identity_resolver=_identity("alpha", "analyst", "analyst")).test_client()
    response = client.get("/findings/" + "f" * (MAX_FINDING_ID_CHARS + 1))
    assert response.status_code == 422
    assert "finding_id exceeds" in response.get_json()["message"]
