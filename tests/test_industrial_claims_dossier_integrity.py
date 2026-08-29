import json
import sqlite3

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database):
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="event-integrity",
        claim_family="TOOLING",
        commercial_basis_ref="basis-integrity",
        cost_evidence_ref="cost-integrity",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger supporting tooling exposure",
        notice_deadline_not_applicable=True,
    )
    return service, result


def _tamper_entitlement(database, result):
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE entitlement_basis SET source_evidence_ids_json=? WHERE tenant_id=? AND entitlement_id=?",
            (json.dumps([result.evidence[0].evidence_id]), "alpha", result.entitlement.entitlement_id),
        )


def test_detail_fails_closed_when_entitlement_evidence_lineage_is_tampered(tmp_path):
    database = tmp_path / "entitlement-tamper.sqlite3"
    service, result = _case(database)
    _tamper_entitlement(database, result)

    with pytest.raises(AssuranceStoreError, match="entitlement evidence lineage does not match"):
        IndustrialClaimsReadModel(database).get_finding(tenant_id="alpha", finding_id=result.finding.finding_id)

    assert service.store.count("findings", "alpha") == 1


def test_review_refuses_corrupt_dossier_before_state_mutation(tmp_path):
    database = tmp_path / "review-preflight.sqlite3"
    service, result = _case(database)
    _tamper_entitlement(database, result)

    with pytest.raises(AssuranceStoreError, match="entitlement evidence lineage does not match"):
        service.review(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            reviewer="reviewer",
            approved=True,
            reason="must not review corrupted dossier",
        )

    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "READY_FOR_REVIEW"
    assert service.store.count("audit_events", "alpha") == 1


def test_action_refuses_corrupt_dossier_before_state_mutation(tmp_path):
    database = tmp_path / "action-preflight.sqlite3"
    service, result = _case(database)
    service.review(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        reviewer="reviewer",
        approved=True,
        reason="internal workflow review",
    )
    _tamper_entitlement(database, result)

    with pytest.raises(AssuranceStoreError, match="entitlement evidence lineage does not match"):
        service.action(tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="operator")

    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "APPROVED"
    assert service.store.count("audit_events", "alpha") == 2


def test_resolve_refuses_corrupt_dossier_before_outcome_evidence_persistence(tmp_path):
    database = tmp_path / "resolve-preflight.sqlite3"
    service, result = _case(database)
    service.review(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        reviewer="reviewer",
        approved=True,
        reason="internal workflow review",
    )
    service.action(tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="operator")
    _tamper_entitlement(database, result)

    with pytest.raises(AssuranceStoreError, match="entitlement evidence lineage does not match"):
        service.resolve(
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            outcome_id="blocked-settlement",
            recovered_amount="5000",
            currency="EUR",
            evidence_ref="bank-blocked",
            evidence_content="must never be persisted for corrupt dossier",
            actor_id="operator",
        )

    assert service.ops.get_state(tenant_id="alpha", finding_id=result.finding.finding_id) == "ACTIONED"
    assert service.ops.outcomes(tenant_id="alpha") == ()
    assert service.store.count("evidence", "alpha") == 3
    assert service.store.count("audit_events", "alpha") == 3


def test_detail_fails_closed_when_recovery_fingerprint_event_is_tampered(tmp_path):
    database = tmp_path / "fingerprint-tamper.sqlite3"
    _service, result = _case(database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE recovery_fingerprints SET event_ref='different-event' WHERE tenant_id=? AND fingerprint=?",
            ("alpha", result.fingerprint.fingerprint),
        )

    with pytest.raises(AssuranceStoreError, match="fingerprint lineage does not match"):
        IndustrialClaimsReadModel(database).get_finding(tenant_id="alpha", finding_id=result.finding.finding_id)


def test_detail_fails_closed_when_deadline_or_calculation_points_outside_finding_evidence(tmp_path):
    database = tmp_path / "evidence-tamper.sqlite3"
    _service, result = _case(database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE deadlines SET basis_evidence_ids_json=? WHERE tenant_id=? AND deadline_id=?",
            (json.dumps(["alpha:foreign-evidence"]), "alpha", result.deadline.deadline_id),
        )

    with pytest.raises(AssuranceStoreError, match="deadline evidence lineage does not match"):
        IndustrialClaimsReadModel(database).get_finding(tenant_id="alpha", finding_id=result.finding.finding_id)

    database2 = tmp_path / "calculation-tamper.sqlite3"
    _service2, result2 = _case(database2)
    with sqlite3.connect(database2) as conn:
        conn.execute(
            "UPDATE calculations SET evidence_ids_json=? WHERE tenant_id=? AND calculation_id=?",
            (json.dumps(["alpha:foreign-evidence"]), "alpha", result2.calculation.calculation_id),
        )

    with pytest.raises(AssuranceStoreError, match="calculation evidence lineage does not match"):
        IndustrialClaimsReadModel(database2).get_finding(tenant_id="alpha", finding_id=result2.finding.finding_id)


def test_case_store_rejects_corrupted_notice_truth_state_on_read(tmp_path):
    database = tmp_path / "notice-tamper.sqlite3"
    service, result = _case(database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE industrial_claim_cases SET notice_deadline_state='VERIFIED_BY_MAGIC' WHERE tenant_id=? AND finding_id=?",
            ("alpha", result.finding.finding_id),
        )

    with pytest.raises(AssuranceStoreError, match="notice truth state is invalid"):
        service.case_store.get(tenant_id="alpha", finding_id=result.finding.finding_id)


def test_outcome_detail_requires_hashed_outcome_evidence_type(tmp_path):
    database = tmp_path / "outcome-tamper.sqlite3"
    service, result = _case(database)
    service.review(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        reviewer="reviewer",
        approved=True,
        reason="reviewed",
    )
    service.action(tenant_id="alpha", finding_id=result.finding.finding_id, actor_id="operator")
    outcome = service.resolve(
        tenant_id="alpha",
        finding_id=result.finding.finding_id,
        outcome_id="settlement-1",
        recovered_amount="5000",
        currency="EUR",
        evidence_ref="bank-1",
        evidence_content="bank evidence of settlement",
        actor_id="operator",
    )
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE evidence SET source_type='cost_evidence' WHERE tenant_id=? AND evidence_id=?",
            ("alpha", outcome.evidence_ref),
        )

    with pytest.raises(AssuranceStoreError, match="outcome evidence lineage not found"):
        IndustrialClaimsReadModel(database).get_finding(tenant_id="alpha", finding_id=result.finding.finding_id)
