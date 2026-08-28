from __future__ import annotations

from dataclasses import dataclass

from .engine import RecoveryResult, evaluate_recoverability
from .recovery_package import RecoveryPackage, build_recovery_package
from .repository import CapacityRepository
from .state import AssistedCaseState


@dataclass(frozen=True)
class ProcessedCase:
    state: AssistedCaseState
    result: RecoveryResult
    recovery_package: RecoveryPackage


def process_state(state: AssistedCaseState) -> ProcessedCase:
    result = evaluate_recoverability(state.recovery_case)
    package = build_recovery_package(
        state.recovery_case,
        result,
        evidence_refs=state.evidence_refs,
        missing_evidence=state.missing_evidence,
        deadline=state.deadline,
    )
    return ProcessedCase(state=state, result=result, recovery_package=package)


def save_and_process(repository: CapacityRepository, state: AssistedCaseState) -> ProcessedCase:
    repository.save(state)
    return process_state(state)


def load_and_process(
    repository: CapacityRepository,
    *,
    tenant_id: str,
    case_id: str,
) -> ProcessedCase:
    state = repository.load(tenant_id=tenant_id, case_id=case_id)
    return process_state(state)
