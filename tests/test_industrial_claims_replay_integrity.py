import sqlite3

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _analyze(service, *, gross_cost="100000", currency="EUR"):
    return service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1", claim_family="TOOLING", commercial_basis_ref="po-1", cost_evidence_ref="ledger-1", currency=currency, commercial_basis_content="signed tooling commercial basis", event_evidence_content="documented customer cancellation", cost_evidence_content=f"tooling ledger supporting gross cost {gross_cost}", gross_cost=gross_cost, resale_reuse="25000", notice_deadline_not_applicable=True,
    )


def test_duplicate_analysis_does_not_downgrade_recovered_finding(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    first = _analyze(service)
    service.review(tenant_id="alpha", finding_id=first.finding.finding_id, reviewer="commercial-reviewer", approved=True, reason="reviewed evidence and amount")
    service.action(tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="operator")
    service.resolve(tenant_id="alpha", finding_id=first.finding.finding_id, outcome_id="alpha:payment-1", recovered_amount="70000", currency="EUR", evidence_ref="bank-1", evidence_content="bank receipt proves 70000 EUR", actor_id="operator")

    replay = _analyze(service)
    assert replay.is_new_recovery is False
    assert replay.finding.state == "RECOVERED"
    assert replay.finding.reviewer == "commercial-reviewer"
    assert replay.finding.decision_reason == "reviewed evidence and amount"
    assert replay.notice_deadline_state == "DECLARED_NONE_FOR_REVIEW"
    assert replay.calculation.output_unit == "EUR"
    assert service.ops.get_state(tenant_id="alpha", finding_id=first.finding.finding_id) == "RECOVERED"
    assert len(service.ops.outcomes(tenant_id="alpha")) == 1


def test_duplicate_analysis_with_changed_economic_input_fails_closed(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    first = _analyze(service)
    service.review(tenant_id="alpha", finding_id=first.finding.finding_id, reviewer="commercial-reviewer", approved=True, reason="reviewed evidence and amount")
    with pytest.raises(AssuranceStoreError, match="immutable evidence id collision|immutable calculation id collision"):
        _analyze(service, gross_cost="110000")
    assert service.ops.get_state(tenant_id="alpha", finding_id=first.finding.finding_id) == "APPROVED"


def test_duplicate_analysis_cannot_rewrite_currency(tmp_path):
    service = IndustrialClaimsService(tmp_path / "currency-replay.sqlite3")
    first = _analyze(service)
    with pytest.raises(AssuranceStoreError, match="immutable calculation id collision"):
        _analyze(service, currency="USD")
    assert service.ops.get_state(tenant_id="alpha", finding_id=first.finding.finding_id) == "READY_FOR_REVIEW"


def test_replay_validation_rolls_back_partial_repairs_on_late_conflict(tmp_path):
    database = tmp_path / "replay-atomic.sqlite3"
    service = IndustrialClaimsService(database)
    first = _analyze(service)
    missing_evidence_id = first.evidence[-1].evidence_id

    with sqlite3.connect(database) as conn:
        conn.execute("DELETE FROM evidence WHERE tenant_id=? AND evidence_id=?", ("alpha", missing_evidence_id))
        conn.execute(
            "UPDATE audit_events SET actor_id='tampered-actor' WHERE tenant_id=? AND event_id=?",
            ("alpha", first.audit.event_id),
        )

    assert service.store.count("evidence", "alpha") == 2
    with pytest.raises(AssuranceStoreError, match="immutable audit event id collision"):
        _analyze(service)

    # The replay attempted to restore the missing evidence before discovering the
    # late audit collision. Atomic replay validation must roll that repair back.
    assert service.store.count("evidence", "alpha") == 2
    with sqlite3.connect(database) as conn:
        row = conn.execute("SELECT 1 FROM evidence WHERE tenant_id=? AND evidence_id=?", ("alpha", missing_evidence_id)).fetchone()
    assert row is None


def test_duplicate_outcome_cannot_rewrite_settlement_evidence(tmp_path):
    service = IndustrialClaimsService(tmp_path / "outcome-replay.sqlite3")
    first = _analyze(service)
    finding_id = first.finding.finding_id
    service.review(tenant_id="alpha", finding_id=finding_id, reviewer="commercial-reviewer", approved=True, reason="reviewed")
    service.action(tenant_id="alpha", finding_id=finding_id, actor_id="operator")
    first_outcome = service.resolve(tenant_id="alpha", finding_id=finding_id, outcome_id="alpha:settlement-1", recovered_amount="70000", currency="EUR", evidence_ref="bank-settlement", evidence_content="immutable bank proof A", actor_id="operator")
    replay = service.resolve(tenant_id="alpha", finding_id=finding_id, outcome_id="alpha:settlement-1", recovered_amount="70000", currency="EUR", evidence_ref="bank-settlement", evidence_content="immutable bank proof A", actor_id="operator")
    assert replay == first_outcome
    assert service.store.count("evidence", "alpha") == 4

    with pytest.raises(AssuranceStoreError, match="immutable evidence id collision"):
        service.resolve(tenant_id="alpha", finding_id=finding_id, outcome_id="alpha:settlement-1", recovered_amount="70000", currency="EUR", evidence_ref="bank-settlement", evidence_content="different bank proof B", actor_id="operator")
    assert len(service.ops.outcomes(tenant_id="alpha")) == 1
