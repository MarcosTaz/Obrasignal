import pytest

from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(service):
    return service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-atomic",
        claim_family="TOOLING",
        commercial_basis_ref="po-atomic",
        cost_evidence_ref="ledger-atomic",
        commercial_basis_content="signed tooling terms for atomic case",
        event_evidence_content="documented cancellation event for atomic case",
        cost_evidence_content="cost ledger for atomic case",
        gross_cost="100000",
        resale_reuse="25000",
        notice_deadline_not_applicable=True,
    )


def test_case_failure_rolls_back_index_and_case_rows(tmp_path, monkeypatch):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    original = service.store._persist_case

    def fail_after_index(_conn, **_kwargs):
        raise RuntimeError("injected case persistence failure")

    monkeypatch.setattr(service.store, "_persist_case", fail_after_index)
    with pytest.raises(RuntimeError, match="injected case persistence failure"):
        _case(service)

    assert service.index.count_entitlements("alpha") == 0
    assert service.index.count_fingerprints("alpha") == 0
    assert service.store.count("evidence", "alpha") == 0
    assert service.store.count("calculations", "alpha") == 0
    assert service.store.count("findings", "alpha") == 0

    monkeypatch.setattr(service.store, "_persist_case", original)
    result = _case(service)

    assert result.is_new_recovery is True
    assert result.finding.state == "READY_FOR_REVIEW"
    assert service.index.count_entitlements("alpha") == 1
    assert service.index.count_fingerprints("alpha") == 1
    assert service.store.count("evidence", "alpha") == 3
    assert service.store.count("findings", "alpha") == 1
