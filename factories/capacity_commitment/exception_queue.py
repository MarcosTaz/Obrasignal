from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from .engine import RecoverabilityState
from .repository import CapacityRepository
from .service import process_state
from .service_ops import ServiceOperationsRepository


class ExceptionType(str, Enum):
    DEADLINE_CRITICAL = "DEADLINE_CRITICAL"
    MONITOR_OVERDUE = "MONITOR_OVERDUE"
    EVIDENCE_BLOCKED = "EVIDENCE_BLOCKED"
    RECOVERY_ACTION_READY = "RECOVERY_ACTION_READY"
    MONITOR_DUE_SOON = "MONITOR_DUE_SOON"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class CaseException:
    monitor_id: str
    engagement_id: str
    case_id: str
    exception_type: ExceptionType
    priority: int
    next_check_on: str
    deadline: str | None
    days_to_deadline: int | None
    days_to_monitor: int
    recoverability_state: RecoverabilityState
    net_exposure: Decimal
    claimable_amount: Decimal
    reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]


def _classify(*, state, processed, monitor, as_of: date):
    result = processed.result
    monitor_date = date.fromisoformat(monitor.next_check_on)
    days_to_monitor = (monitor_date - as_of).days
    deadline_date = date.fromisoformat(state.deadline) if state.deadline else None
    days_to_deadline = None if deadline_date is None else (deadline_date - as_of).days

    if result.net_exposure > Decimal("0") and days_to_deadline is not None and days_to_deadline <= 7:
        return ExceptionType.DEADLINE_CRITICAL, 100, days_to_monitor, days_to_deadline
    if days_to_monitor <= 0:
        return ExceptionType.MONITOR_OVERDUE, 90, days_to_monitor, days_to_deadline
    if result.recoverability_state is RecoverabilityState.UNKNOWN:
        return ExceptionType.EVIDENCE_BLOCKED, 80, days_to_monitor, days_to_deadline
    if result.recoverability_state is RecoverabilityState.RECOVERABLE and result.claimable_amount > Decimal("0"):
        return ExceptionType.RECOVERY_ACTION_READY, 70, days_to_monitor, days_to_deadline
    if days_to_monitor <= 7:
        return ExceptionType.MONITOR_DUE_SOON, 50, days_to_monitor, days_to_deadline
    return ExceptionType.NO_ACTION, 0, days_to_monitor, days_to_deadline


def build_exception_queue(
    repository: CapacityRepository,
    *,
    tenant_id: str,
    as_of: date,
    include_no_action: bool = False,
) -> tuple[CaseException, ...]:
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    service_ops = ServiceOperationsRepository(repository.db_path)
    items = []
    for monitor in service_ops.list_active_monitors(tenant_id=tenant_id):
        state = repository.load(tenant_id=tenant_id, case_id=monitor.case_id)
        processed = process_state(state, as_of_date=as_of)
        exception_type, priority, days_to_monitor, days_to_deadline = _classify(
            state=state,
            processed=processed,
            monitor=monitor,
            as_of=as_of,
        )
        if exception_type is ExceptionType.NO_ACTION and not include_no_action:
            continue
        items.append(
            CaseException(
                monitor_id=monitor.monitor_id,
                engagement_id=monitor.engagement_id,
                case_id=monitor.case_id,
                exception_type=exception_type,
                priority=priority,
                next_check_on=monitor.next_check_on,
                deadline=state.deadline,
                days_to_deadline=days_to_deadline,
                days_to_monitor=days_to_monitor,
                recoverability_state=processed.result.recoverability_state,
                net_exposure=processed.result.net_exposure,
                claimable_amount=(
                    processed.result.claimable_amount
                    if processed.result.recoverability_state is RecoverabilityState.RECOVERABLE
                    else Decimal("0")
                ),
                reasons=processed.result.reasons,
                missing_evidence=state.missing_evidence,
            )
        )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                -item.priority,
                item.days_to_deadline if item.days_to_deadline is not None else 10**9,
                item.days_to_monitor,
                item.case_id,
            ),
        )
    )
