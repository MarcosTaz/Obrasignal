import sqlite3

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _initial(service: IndustrialClaimsService, *, event_ref: str = "cancel-1", customer_ref: str = "oem-1"):
    return service.analyze(
        tenant_id="alpha", actor_id="analyst-1", customer_ref=customer_ref, program_ref="program-1",
        event_ref=event_ref, claim_family="TOOLING", commercial_basis_ref=f"basis-{event_ref}",
        cost_evidence_ref=f"cost-{event_ref}-1", gross_cost="10000", currency="EUR",
        commercial_basis_content="signed tooling agreement", event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger v1", notice_deadline_not_applicable=True,
    )


def _amend(service: IndustrialClaimsService, first):
    metadata = service.case_store.get(tenant_id="alpha", finding_id=first.finding.finding_id)
    return amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-2",
        customer_ref=metadata.customer_ref, program_ref=metadata.program_ref, event_ref=metadata.event_ref,
        claim_family=metadata.claim_family, commercial_basis_ref=f"basis-{metadata.event_ref}",
        cost_evidence_ref=f"cost-{metadata.event_ref}-2", gross_cost="12000", currency="EUR",
        commercial_basis_content="signed tooling agreement", event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger v2", notice_deadline_not_applicable=True,
    )


def test_current_revision_fails_closed_when_predecessor_is_missing(tmp_path):
    database = tmp_path / "missing-predecessor.sqlite3"
    service = IndustrialClaimsService(database)
    first = _initial(service)
    second = _amend(service, first)

    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE industrial_claim_revisions SET supersedes_finding_id='alpha:missing' WHERE tenant_id=? AND finding_id=?",
            ("alpha", second.finding.finding_id),
        )

    with pytest.raises(AssuranceStoreError, match="predecessor is missing"):
        service.revision_store.require_current(tenant_id="alpha", finding_id=second.finding.finding_id)
    with pytest.raises(AssuranceStoreError, match="predecessor is missing"):
        IndustrialClaimsReadModel(database).get_finding(tenant_id="alpha", finding_id=second.finding.finding_id)
    with pytest.raises(AssuranceStoreError, match="predecessor is missing"):
        service.review(
            tenant_id="alpha", finding_id=second.finding.finding_id, reviewer="reviewer",
            approved=True, reason="must not mutate corrupted revision lineage",
        )
    assert service.ops.get_state(tenant_id="alpha", finding_id=second.finding.finding_id) == "READY_FOR_REVIEW"


def test_current_revision_fails_closed_when_predecessor_has_different_fingerprint(tmp_path):
    database = tmp_path / "cross-fingerprint-predecessor.sqlite3"
    service = IndustrialClaimsService(database)
    first = _initial(service, event_ref="cancel-a", customer_ref="oem-a")
    second = _amend(service, first)
    foreign = _initial(service, event_ref="cancel-b", customer_ref="oem-b")

    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE industrial_claim_revisions SET supersedes_finding_id=? WHERE tenant_id=? AND finding_id=?",
            (foreign.finding.finding_id, "alpha", second.finding.finding_id),
        )

    with pytest.raises(AssuranceStoreError, match="predecessor fingerprint is inconsistent"):
        service.revision_store.require_current(tenant_id="alpha", finding_id=second.finding.finding_id)


def test_historical_detail_fails_closed_on_ambiguous_direct_successor(tmp_path):
    database = tmp_path / "ambiguous-successor.sqlite3"
    service = IndustrialClaimsService(database)
    first = _initial(service)
    second = _amend(service, first)
    fingerprint = first.fingerprint.fingerprint

    with sqlite3.connect(database) as conn:
        conn.execute(
            "INSERT INTO industrial_claim_revisions(finding_id,tenant_id,recovery_fingerprint,revision,supersedes_finding_id,is_current) VALUES(?,?,?,?,?,0)",
            ("alpha:rogue-r99", "alpha", fingerprint, 99, first.finding.finding_id),
        )

    with pytest.raises(AssuranceStoreError, match="ambiguous direct successor"):
        IndustrialClaimsReadModel(database).get_finding(tenant_id="alpha", finding_id=first.finding.finding_id)

    assert service.revision_store.require_current(tenant_id="alpha", finding_id=second.finding.finding_id).revision == 2
