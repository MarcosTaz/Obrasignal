import sqlite3
from datetime import date

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.shared_platform import AuditEvent, TenantContext
from vertical_apps.contractcredit import ContractCreditService


def _ready(tmp_path):
    service = ContractCreditService(tmp_path / "case.sqlite3")
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-1",
        contract_ref="msa",
        incident_ref="incident",
        monthly_fee="1000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 30),
    )
    return service, result["finding_id"]


def _audit_types(service):
    with sqlite3.connect(service.store.path) as conn:
        rows = conn.execute(
            "SELECT event_type,actor_id FROM audit_events WHERE tenant_id=? ORDER BY rowid",
            ("tenant-a",),
        ).fetchall()
    return rows


def test_review_action_and_resolution_append_actor_audit(tmp_path):
    service, finding_id = _ready(tmp_path)

    service.ops.review(
        tenant_id="tenant-a",
        finding_id=finding_id,
        reviewer="reviewer-1",
        approved=True,
        reason="supported",
    )
    service.ops.action(tenant_id="tenant-a", finding_id=finding_id, actor_id="operator-1")
    service.ops.resolve(
        tenant_id="tenant-a",
        finding_id=finding_id,
        outcome_id="outcome-1",
        recovered_amount="100",
        currency="EUR",
        evidence_ref="credit-note-1",
        actor_id="operator-2",
    )

    audit = _audit_types(service)
    assert ("finding_reviewed", "reviewer-1") in audit
    assert ("finding_actioned", "operator-1") in audit
    assert ("finding_resolved", "operator-2") in audit


def test_action_and_audit_commit_or_rollback_together(tmp_path):
    service, finding_id = _ready(tmp_path)
    service.ops.review(
        tenant_id="tenant-a",
        finding_id=finding_id,
        reviewer="reviewer-1",
        approved=True,
        reason="supported",
    )

    conflicting = AuditEvent.create(
        event_id=f"tenant-a:{finding_id}:action",
        context=TenantContext(tenant_id="tenant-a", actor_id="operator-existing", roles=("operator",)),
        event_type="finding_actioned",
        subject_ref=finding_id,
        payload={"state": "DIFFERENT"},
    )
    service.store.append_audit(conflicting)

    with pytest.raises(AssuranceStoreError, match="immutable audit event id collision"):
        service.ops.action(tenant_id="tenant-a", finding_id=finding_id, actor_id="operator-1")

    assert service.ops.get_state(tenant_id="tenant-a", finding_id=finding_id) == "APPROVED"
