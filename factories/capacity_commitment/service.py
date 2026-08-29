from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .engine import RecoveryResult, evaluate_recoverability
from .recovery_package import RecoveryPackage, build_recovery_package
from .repository import CapacityRepository
from .state import AssistedCaseState, dump_state
from .temporal import assess_temporal_state


@dataclass(frozen=True)
class ProcessedCase:
    state: AssistedCaseState
    result: RecoveryResult
    recovery_package: RecoveryPackage


def process_state(
    state: AssistedCaseState,
    *,
    as_of_date: date | None = None,
) -> ProcessedCase:
    # The engine validates economic semantics, while the persisted-state envelope
    # validates identity, contract anchors, evidence references and deadline
    # consistency. Apply both before producing any reviewable output.
    dump_state(state)
    temporal = assess_temporal_state(state, as_of_date=as_of_date)
    result = evaluate_recoverability(temporal.effective_case)
    package = build_recovery_package(
        temporal.effective_case,
        result,
        evidence_refs=state.evidence_refs,
        missing_evidence=state.missing_evidence,
        deadline=state.deadline,
        assessment_date=temporal.assessment_date.isoformat(),
        deadline_expired_by_date=temporal.deadline_expired_by_date,
    )
    return ProcessedCase(state=state, result=result, recovery_package=package)


def save_and_process(repository: CapacityRepository, state: AssistedCaseState) -> ProcessedCase:
    """Validate and assess first; persist only a state that the engine accepts."""

    processed = process_state(state)
    repository.save(state)
    return processed


def _validate_revision_identity(parent: AssistedCaseState, child: AssistedCaseState) -> None:
    """A revision may change evidence/economics, never the bounded case identity."""

    identity = {
        "company_id": (parent.company_id, child.company_id),
        "customer_id": (parent.customer_id, child.customer_id),
        "program_id": (parent.program_id, child.program_id),
        "currency": (parent.recovery_case.currency, child.recovery_case.currency),
    }
    mismatches = [name for name, (before, after) in identity.items() if before != after]
    if mismatches:
        raise ValueError(
            "revision identity mismatch: " + ", ".join(sorted(mismatches))
        )


def save_revision_and_process(
    repository: CapacityRepository,
    state: AssistedCaseState,
    *,
    parent_case_id: str,
) -> ProcessedCase:
    """Validate a changed source state, then persist it as an immutable revision."""

    parent = repository.load(tenant_id=state.tenant_id, case_id=parent_case_id)
    _validate_revision_identity(parent, state)
    processed = process_state(state)
    repository.create_revision(state, parent_case_id=parent_case_id)
    return processed


def load_and_process(
    repository: CapacityRepository,
    *,
    tenant_id: str,
    case_id: str,
) -> ProcessedCase:
    state = repository.load(tenant_id=tenant_id, case_id=case_id)
    return process_state(state)
