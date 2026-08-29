import sqlite3
from decimal import Decimal

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.service_ops import (
    MonitoringPlan,
    ServiceOperationsRepository,
    SupportCategory,
    SupportEvent,
    SupportEventType,
    SupportTicket,
)
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.workflow import (
    Engagement,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowRepository,
)


def state(case_id="case-1", *, tenant="tenant-a", company="supplier-1"):
    return AssistedCaseState(
        tenant_id=tenant,
        company_id=company,
        customer_id="oem-1",
        program_id="program-1",
        recovery_case=case(case_id, currency="EUR"),
        evidence_refs=("contract:1",),
        contract_id="lta-1",
        deadline="2099-09-30",
    )


def seed_operations(db_path):
    cases = CapacityRepository(str(db_path))
    cases.save(state())
    workflow = WorkflowRepository(str(db_path))
    workflow.save_engagement(
        Engagement(
            tenant_id="tenant-a",
            engagement_id="eng-1",
            company_id="supplier-1",
            customer_id="oem-1",
            program_id="program-1",
            currency="EUR",
        )
    )
    workflow.append_event(
        WorkflowEvent(
            tenant_id="tenant-a",
            event_id="link",
            engagement_id="eng-1",
            event_type=WorkflowEventType.CASE_LINKED,
            occurred_at="2026-08-29T20:00:00Z",
            case_id="case-1",
            external_ref="buyer-thread:1",
        )
    )
    workflow.append_event(
        WorkflowEvent(
            tenant_id="tenant-a",
            event_id="invoice",
            engagement_id="eng-1",
            event_type=WorkflowEventType.OUR_INVOICE_ISSUED,
            occurred_at="2026-08-29T21:00:00Z",
            amount=Decimal("3500"),
            currency="EUR",
            external_ref="invoice:synthetic-1",
        )
    )
    ops = ServiceOperationsRepository(str(db_path))
    ops.save_monitor(
        MonitoringPlan(
            tenant_id="tenant-a",
            monitor_id="monitor-v1",
            engagement_id="eng-1",
            case_id="case-1",
            cadence_days=30,
            next_check_on="2026-09-30",
        )
    )
    ops.open_ticket(
        SupportTicket(
            tenant_id="tenant-a",
            ticket_id="ticket-1",
            engagement_id="eng-1",
            category=SupportCategory.CALCULATION,
            summary="Explain mitigation",
            opened_at="2026-08-29T21:30:00Z",
            case_id="case-1",
        )
    )
    ops.append_support_event(
        SupportEvent(
            tenant_id="tenant-a",
            support_event_id="support-1",
            ticket_id="ticket-1",
            event_type=SupportEventType.ACKNOWLEDGED,
            occurred_at="2026-08-29T21:35:00Z",
            note="Acknowledged",
        )
    )
    return cases, workflow, ops


def test_backup_restore_rewinds_workflow_monitoring_and_support_together(tmp_path):
    live = tmp_path / "live.db"
    backup = tmp_path / "backup.db"
    cases, workflow, ops = seed_operations(live)
    cases.backup_to(str(backup))

    workflow.append_event(
        WorkflowEvent(
            tenant_id="tenant-a",
            event_id="post-backup-payment",
            engagement_id="eng-1",
            event_type=WorkflowEventType.OUR_PAYMENT_RECEIVED,
            occurred_at="2026-08-30T10:00:00Z",
            amount=Decimal("3500"),
            currency="EUR",
            external_ref="payment:synthetic",
        )
    )
    ops.save_monitor(
        MonitoringPlan(
            tenant_id="tenant-a",
            monitor_id="monitor-v2",
            engagement_id="eng-1",
            case_id="case-1",
            cadence_days=14,
            next_check_on="2026-09-14",
            supersedes_monitor_id="monitor-v1",
        )
    )
    ops.append_support_event(
        SupportEvent(
            tenant_id="tenant-a",
            support_event_id="support-2",
            ticket_id="ticket-1",
            event_type=SupportEventType.RESOLVED,
            occurred_at="2026-08-30T10:10:00Z",
            note="Resolved after backup",
        )
    )

    cases.restore_from(str(backup))

    workflow2 = WorkflowRepository(str(live))
    ops2 = ServiceOperationsRepository(str(live))
    events = workflow2.list_events(tenant_id="tenant-a", engagement_id="eng-1")
    assert [event.event_id for event in events] == ["invoice", "link"] or [event.event_id for event in events] == ["link", "invoice"]
    summary = workflow2.summary(tenant_id="tenant-a", engagement_id="eng-1")
    assert summary.our_invoice_issued == Decimal("3500")
    assert summary.our_payment_received == Decimal("0")
    assert [m.monitor_id for m in ops2.list_active_monitors(tenant_id="tenant-a")] == ["monitor-v1"]
    support = ops2.support_state(tenant_id="tenant-a", ticket_id="ticket-1")
    assert support.status == "OPEN"
    assert support.event_count == 1


def test_restore_rejects_workflow_event_with_foreign_engagement_before_live_mutation(tmp_path):
    live = tmp_path / "live.db"
    bad = tmp_path / "bad.db"
    live_cases, live_workflow, _ = seed_operations(live)
    seed_operations(bad)
    with sqlite3.connect(bad) as conn:
        conn.execute(
            "UPDATE capacity_commitment_workflow_events SET tenant_id='tenant-b' WHERE event_id='link'"
        )

    with pytest.raises(ValueError, match="missing or cross-tenant engagement"):
        live_cases.restore_from(str(bad))

    assert live_workflow.load_engagement(tenant_id="tenant-a", engagement_id="eng-1").company_id == "supplier-1"
    assert len(live_workflow.list_events(tenant_id="tenant-a", engagement_id="eng-1")) == 2


def test_restore_rejects_workflow_case_identity_mismatch(tmp_path):
    live = tmp_path / "live.db"
    bad = tmp_path / "bad.db"
    live_cases, _, _ = seed_operations(live)
    bad_cases, bad_workflow, _ = seed_operations(bad)
    bad_cases.save(state("wrong-company", company="supplier-2"))
    with sqlite3.connect(bad) as conn:
        conn.execute(
            "UPDATE capacity_commitment_workflow_events SET case_id='wrong-company' WHERE event_id='link'"
        )

    with pytest.raises(ValueError, match="case/engagement identity mismatch"):
        live_cases.restore_from(str(bad))


def test_restore_rejects_monitor_supersession_cycle(tmp_path):
    live = tmp_path / "live.db"
    bad = tmp_path / "bad.db"
    live_cases, _, _ = seed_operations(live)
    _bad_cases, _bad_workflow, bad_ops = seed_operations(bad)
    bad_ops.save_monitor(
        MonitoringPlan(
            tenant_id="tenant-a",
            monitor_id="monitor-v2",
            engagement_id="eng-1",
            case_id="case-1",
            cadence_days=14,
            next_check_on="2026-09-14",
            supersedes_monitor_id="monitor-v1",
        )
    )
    with sqlite3.connect(bad) as conn:
        conn.execute(
            "UPDATE capacity_commitment_monitoring_plans SET supersedes_monitor_id='monitor-v2' WHERE monitor_id='monitor-v1'"
        )

    with pytest.raises(ValueError, match="supersession cycle"):
        live_cases.restore_from(str(bad))


def test_restore_rejects_support_event_with_foreign_ticket(tmp_path):
    live = tmp_path / "live.db"
    bad = tmp_path / "bad.db"
    live_cases, _, _ = seed_operations(live)
    seed_operations(bad)
    with sqlite3.connect(bad) as conn:
        conn.execute(
            "UPDATE capacity_commitment_support_events SET tenant_id='tenant-b' WHERE support_event_id='support-1'"
        )

    with pytest.raises(ValueError, match="missing or cross-tenant ticket"):
        live_cases.restore_from(str(bad))


def test_restore_legacy_backup_without_operational_group_clears_newer_operations(tmp_path):
    live = tmp_path / "live.db"
    legacy = tmp_path / "legacy.db"
    live_cases, _, _ = seed_operations(live)

    # Build a valid current backup then deliberately remove the entire newer
    # operational groups to emulate a historical pre-operations snapshot.
    live_cases.backup_to(str(legacy))
    with sqlite3.connect(legacy) as conn:
        conn.execute("DROP TABLE capacity_commitment_support_events")
        conn.execute("DROP TABLE capacity_commitment_support_tickets")
        conn.execute("DROP TABLE capacity_commitment_monitoring_plans")
        conn.execute("DROP TABLE capacity_commitment_workflow_events")
        conn.execute("DROP TABLE capacity_commitment_engagements")

    live_cases.restore_from(str(legacy))
    workflow = WorkflowRepository(str(live))
    ops = ServiceOperationsRepository(str(live))
    assert workflow.list_engagements(tenant_id="tenant-a") == []
    assert ops.list_active_monitors(tenant_id="tenant-a") == []


def test_restore_rejects_half_present_workflow_group(tmp_path):
    live = tmp_path / "live.db"
    bad = tmp_path / "bad.db"
    live_cases = CapacityRepository(str(live))
    seed_operations(bad)
    with sqlite3.connect(bad) as conn:
        conn.execute("DROP TABLE capacity_commitment_workflow_events")

    with pytest.raises(ValueError, match="incomplete workflow schema"):
        live_cases.restore_from(str(bad))


def test_direct_repository_revision_cannot_change_economic_identity(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    repo.save(state("root"))
    for field, child in (
        ("company_id", state("child-company", company="supplier-2")),
        (
            "customer_id",
            AssistedCaseState(
                tenant_id="tenant-a",
                company_id="supplier-1",
                customer_id="oem-2",
                program_id="program-1",
                recovery_case=case("child-customer", currency="EUR"),
                evidence_refs=("contract:1",),
                contract_id="lta-1",
                deadline="2099-09-30",
            ),
        ),
    ):
        with pytest.raises(ValueError, match=field):
            repo.create_revision(child, parent_case_id="root")
    assert repo.list_case_ids(tenant_id="tenant-a") == ["root"]
