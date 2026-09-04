from datetime import date
from decimal import Decimal

from factories.capacity_commitment.engine import RecoverabilityState
from factories.capacity_commitment.exception_queue import ExceptionType, build_exception_queue
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.service_ops import MonitoringPlan, ServiceOperationsRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.workflow import Engagement, WorkflowRepository


def save_state(repo, case_id, *, deadline, **case_overrides):
    repo.save(
        AssistedCaseState(
            tenant_id="tenant-a",
            company_id="supplier-1",
            customer_id="oem-1",
            program_id="program-1",
            period_id="2026Q2",
            unit="parts",
            recovery_case=case(case_id, **case_overrides),
            evidence_refs=("synthetic:source",),
            missing_evidence=(),
            deadline=deadline,
            contract_id="lta-1",
        )
    )


def setup_monitor(tmp_path, case_id, *, deadline="2026-09-30", next_check="2026-09-10", **case_overrides):
    db = tmp_path / "capacity.db"
    repo = CapacityRepository(str(db))
    save_state(repo, case_id, deadline=deadline, **case_overrides)
    workflow = WorkflowRepository(str(db))
    workflow.save_engagement(Engagement("tenant-a", "eng-1", "supplier-1", "oem-1", "program-1", "EUR"))
    ServiceOperationsRepository(str(db)).save_monitor(
        MonitoringPlan("tenant-a", "mon-1", "eng-1", case_id, 30, next_check)
    )
    return repo


def test_deadline_risk_outranks_monitor_and_never_upgrades_unknown_to_claimable(tmp_path):
    repo = setup_monitor(
        tmp_path,
        "case-unknown",
        deadline="2026-09-08",
        next_check="2026-09-20",
        explicit_recovery_right=None,
    )
    queue = build_exception_queue(repo, tenant_id="tenant-a", as_of=date(2026, 9, 4))
    item = queue[0]
    assert item.exception_type is ExceptionType.DEADLINE_CRITICAL
    assert item.priority == 100
    assert item.recoverability_state is RecoverabilityState.UNKNOWN
    assert item.net_exposure == Decimal("100000")
    assert item.claimable_amount == Decimal("0")


def test_overdue_monitor_prioritizes_before_ready_action(tmp_path):
    repo = setup_monitor(tmp_path, "case-ready", deadline="2026-12-31", next_check="2026-09-01")
    item = build_exception_queue(repo, tenant_id="tenant-a", as_of=date(2026, 9, 4))[0]
    assert item.exception_type is ExceptionType.MONITOR_OVERDUE
    assert item.priority == 90
    assert item.claimable_amount == Decimal("100000")


def test_unknown_evidence_blocked_has_zero_claimable_in_queue(tmp_path):
    repo = setup_monitor(
        tmp_path,
        "case-blocked",
        deadline="2026-12-31",
        next_check="2026-10-01",
        actuals_complete=None,
    )
    item = build_exception_queue(repo, tenant_id="tenant-a", as_of=date(2026, 9, 4))[0]
    assert item.exception_type is ExceptionType.EVIDENCE_BLOCKED
    assert item.recoverability_state is RecoverabilityState.UNKNOWN
    assert item.claimable_amount == Decimal("0")
    assert "actuals_completeness_unknown" in item.reasons


def test_recoverable_case_becomes_action_ready_not_payment_proof(tmp_path):
    repo = setup_monitor(tmp_path, "case-ready", deadline="2026-12-31", next_check="2026-10-01")
    item = build_exception_queue(repo, tenant_id="tenant-a", as_of=date(2026, 9, 4))[0]
    assert item.exception_type is ExceptionType.RECOVERY_ACTION_READY
    assert item.recoverability_state is RecoverabilityState.RECOVERABLE
    assert item.claimable_amount == Decimal("100000")


def test_no_action_case_is_hidden_by_default_and_visible_on_request(tmp_path):
    repo = setup_monitor(
        tmp_path,
        "case-zero",
        deadline="2026-12-31",
        next_check="2026-10-20",
        actual_units=Decimal("100000"),
    )
    assert build_exception_queue(repo, tenant_id="tenant-a", as_of=date(2026, 9, 4)) == ()
    queue = build_exception_queue(
        repo,
        tenant_id="tenant-a",
        as_of=date(2026, 9, 4),
        include_no_action=True,
    )
    assert queue[0].exception_type is ExceptionType.NO_ACTION
    assert queue[0].claimable_amount == Decimal("0")
