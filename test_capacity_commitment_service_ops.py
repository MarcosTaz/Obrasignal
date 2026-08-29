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
from factories.capacity_commitment.workflow import Engagement, WorkflowRepository


def setup_scope(db):
    cases = CapacityRepository(str(db))
    workflow = WorkflowRepository(str(db))
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
    cases.save(
        AssistedCaseState(
            tenant_id="tenant-a",
            company_id="supplier-1",
            customer_id="oem-1",
            program_id="program-1",
            recovery_case=case("case-1", currency="EUR"),
            evidence_refs=("contract:1",),
            contract_id="lta-1",
            deadline="2099-09-30",
        )
    )
    return cases, workflow


def test_monitor_plan_is_immutable_and_supersession_preserves_history(tmp_path):
    db = tmp_path / "capacity.db"
    setup_scope(db)
    ops = ServiceOperationsRepository(str(db))
    first = MonitoringPlan(
        tenant_id="tenant-a",
        monitor_id="monitor-v1",
        engagement_id="eng-1",
        case_id="case-1",
        cadence_days=30,
        next_check_on="2026-09-30",
    )
    second = MonitoringPlan(
        tenant_id="tenant-a",
        monitor_id="monitor-v2",
        engagement_id="eng-1",
        case_id="case-1",
        cadence_days=14,
        next_check_on="2026-09-14",
        supersedes_monitor_id="monitor-v1",
    )
    assert ops.save_monitor(first) is True
    assert ops.save_monitor(first) is False
    assert ops.save_monitor(second) is True
    assert ops.load_monitor(tenant_id="tenant-a", monitor_id="monitor-v1") == first
    assert ops.list_active_monitors(tenant_id="tenant-a") == [second]


def test_monitor_rejects_invalid_cadence_cross_tenant_or_wrong_case(tmp_path):
    db = tmp_path / "capacity.db"
    setup_scope(db)
    ops = ServiceOperationsRepository(str(db))
    with pytest.raises(ValueError, match="cadence_days"):
        ops.save_monitor(
            MonitoringPlan("tenant-a", "bad", "eng-1", "case-1", 0, "2026-09-30")
        )
    with pytest.raises(KeyError):
        ops.save_monitor(
            MonitoringPlan("tenant-b", "foreign", "eng-1", "case-1", 30, "2026-09-30")
        )


def test_support_ticket_is_tenant_and_case_scoped(tmp_path):
    db = tmp_path / "capacity.db"
    setup_scope(db)
    ops = ServiceOperationsRepository(str(db))
    ticket = SupportTicket(
        tenant_id="tenant-a",
        ticket_id="ticket-1",
        engagement_id="eng-1",
        category=SupportCategory.CALCULATION,
        summary="Please explain the mitigation line.",
        opened_at="2026-08-29T20:00:00Z",
        case_id="case-1",
    )
    assert ops.open_ticket(ticket) is True
    assert ops.open_ticket(ticket) is False
    assert ops.load_ticket(tenant_id="tenant-a", ticket_id="ticket-1") == ticket
    with pytest.raises(KeyError):
        ops.load_ticket(tenant_id="tenant-b", ticket_id="ticket-1")


def test_support_events_are_append_only_and_drive_resolve_reopen_state(tmp_path):
    db = tmp_path / "capacity.db"
    setup_scope(db)
    ops = ServiceOperationsRepository(str(db))
    ops.open_ticket(
        SupportTicket(
            tenant_id="tenant-a",
            ticket_id="ticket-1",
            engagement_id="eng-1",
            category=SupportCategory.DATA,
            summary="Actuals file contains duplicate releases.",
            opened_at="2026-08-29T20:00:00Z",
            case_id="case-1",
        )
    )
    resolved = SupportEvent(
        tenant_id="tenant-a",
        support_event_id="support-1",
        ticket_id="ticket-1",
        event_type=SupportEventType.RESOLVED,
        occurred_at="2026-08-29T21:00:00Z",
        note="Deduplication source reviewed.",
    )
    reopened = SupportEvent(
        tenant_id="tenant-a",
        support_event_id="support-2",
        ticket_id="ticket-1",
        event_type=SupportEventType.REOPENED,
        occurred_at="2026-08-30T09:00:00Z",
        note="New release file received.",
    )
    assert ops.append_support_event(resolved) is True
    assert ops.append_support_event(resolved) is False
    assert ops.support_state(tenant_id="tenant-a", ticket_id="ticket-1").status == "RESOLVED"
    assert ops.append_support_event(reopened) is True
    state = ops.support_state(tenant_id="tenant-a", ticket_id="ticket-1")
    assert state.status == "OPEN"
    assert state.event_count == 2
    assert state.latest_event_type == "REOPENED"


def test_support_event_cannot_attach_to_foreign_ticket(tmp_path):
    db = tmp_path / "capacity.db"
    setup_scope(db)
    ops = ServiceOperationsRepository(str(db))
    ops.open_ticket(
        SupportTicket(
            tenant_id="tenant-a",
            ticket_id="ticket-1",
            engagement_id="eng-1",
            category=SupportCategory.OTHER,
            summary="Question",
            opened_at="2026-08-29T20:00:00Z",
        )
    )
    with pytest.raises(KeyError):
        ops.append_support_event(
            SupportEvent(
                tenant_id="tenant-b",
                support_event_id="foreign",
                ticket_id="ticket-1",
                event_type=SupportEventType.NOTE,
                occurred_at="2026-08-29T21:00:00Z",
            )
        )
