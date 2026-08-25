"""Cross-cutting resilience contract for ObraSignal.

This module is deliberately non-runtime and side-effect free.  It owns the
previously unowned *governance/test* semantics between an injected failure and a
truthful degraded/recovery result.  Domain owners remain authoritative for
storage, Auth, Billing, source health, notifications and production readiness.

The core invariants are intentionally conservative:

* UNKNOWN never becomes HEALTHY;
* partial success never becomes complete success;
* uncertain/committed writes are never blindly retried without proven
  idempotency;
* retries are bounded;
* a responding service is not the same as verified recovery;
* verified recovery requires explicit tenant, data-integrity and retry-drain
  evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, FrozenSet, Mapping, Optional, Sequence, Tuple


CONTRACT_VERSION = "resilience.v1"
_TOKEN = re.compile(r"^[A-Za-z0-9_.:/-]{1,96}$")


class ServiceState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class FailureClass(str, Enum):
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    PARTIAL_RESPONSE = "PARTIAL_RESPONSE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    CORRUPT_STATE = "CORRUPT_STATE"
    AUTH_UNAVAILABLE = "AUTH_UNAVAILABLE"
    BILLING_UNAVAILABLE = "BILLING_UNAVAILABLE"
    SOURCE_STALE = "SOURCE_STALE"
    NOTIFICATION_DELIVERY_FAILURE = "NOTIFICATION_DELIVERY_FAILURE"
    UNKNOWN = "UNKNOWN"


class MutationState(str, Enum):
    NONE = "NONE"
    UNCOMMITTED = "UNCOMMITTED"
    COMMITTED = "COMMITTED"
    UNKNOWN = "UNKNOWN"


class IdempotencyState(str, Enum):
    PROVEN = "PROVEN"
    NOT_PROVEN = "NOT_PROVEN"
    UNKNOWN = "UNKNOWN"


class RetryDecision(str, Enum):
    RETRY = "RETRY"
    STOP_NON_RETRYABLE = "STOP_NON_RETRYABLE"
    STOP_UNSAFE_REPLAY = "STOP_UNSAFE_REPLAY"
    STOP_EXHAUSTED = "STOP_EXHAUSTED"
    STOP_SAFETY_VIOLATION = "STOP_SAFETY_VIOLATION"


class RecoveryState(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SERVICE_RESTORED = "SERVICE_RESTORED"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


DEFAULT_RETRYABLE: FrozenSet[FailureClass] = frozenset(
    {
        FailureClass.TIMEOUT,
        FailureClass.DEPENDENCY_UNAVAILABLE,
        FailureClass.AUTH_UNAVAILABLE,
        FailureClass.BILLING_UNAVAILABLE,
        FailureClass.NOTIFICATION_DELIVERY_FAILURE,
    }
)


@dataclass(frozen=True)
class RetryPolicy:
    """A bounded deterministic retry policy used for tests/governance.

    ``max_attempts`` includes the first attempt.  Backoff is capped and has no
    jitter here so regression tests remain deterministic.  Runtime owners may
    implement their own jitter while preserving the same safety invariants.
    """

    max_attempts: int = 3
    base_backoff_ms: int = 250
    max_backoff_ms: int = 4_000
    retryable: FrozenSet[FailureClass] = DEFAULT_RETRYABLE

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 8:
            raise ValueError("max_attempts must be between 1 and 8")
        if not 0 <= self.base_backoff_ms <= 60_000:
            raise ValueError("base_backoff_ms out of bounds")
        if not self.base_backoff_ms <= self.max_backoff_ms <= 120_000:
            raise ValueError("max_backoff_ms out of bounds")
        if FailureClass.UNKNOWN in self.retryable:
            raise ValueError("UNKNOWN may never be declared retryable")

    def delay_after(self, attempt: int) -> int:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        exponent = min(attempt - 1, 16)
        return min(self.base_backoff_ms * (2**exponent), self.max_backoff_ms)


@dataclass(frozen=True)
class AttemptEvidence:
    failure_class: FailureClass
    attempt: int
    mutation_state: MutationState = MutationState.NONE
    idempotency: IdempotencyState = IdempotencyState.UNKNOWN
    tenant_safe: bool = True
    truth_preserved: bool = True

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")


@dataclass(frozen=True)
class RetryVerdict:
    decision: RetryDecision
    delay_ms: Optional[int]


def decide_retry(evidence: AttemptEvidence, policy: RetryPolicy) -> RetryVerdict:
    """Return the only retry decision justified by current evidence.

    Safety and replay uncertainty beat availability.  In particular, a write
    that may have committed cannot be retried unless idempotency is explicitly
    proven by the owning contract.
    """

    if not evidence.tenant_safe or not evidence.truth_preserved:
        return RetryVerdict(RetryDecision.STOP_SAFETY_VIOLATION, None)

    if evidence.attempt >= policy.max_attempts:
        return RetryVerdict(RetryDecision.STOP_EXHAUSTED, None)

    if evidence.failure_class not in policy.retryable:
        return RetryVerdict(RetryDecision.STOP_NON_RETRYABLE, None)

    uncertain_write = evidence.mutation_state in {
        MutationState.COMMITTED,
        MutationState.UNKNOWN,
    }
    if uncertain_write and evidence.idempotency is not IdempotencyState.PROVEN:
        return RetryVerdict(RetryDecision.STOP_UNSAFE_REPLAY, None)

    return RetryVerdict(RetryDecision.RETRY, policy.delay_after(evidence.attempt))


@dataclass(frozen=True)
class DegradedModeContract:
    required: Tuple[str, ...]
    optional: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        all_names = self.required + self.optional
        if not self.required:
            raise ValueError("at least one required capability is needed")
        if len(set(all_names)) != len(all_names):
            raise ValueError("capability names must be unique")
        for name in all_names:
            if not _TOKEN.fullmatch(name):
                raise ValueError(f"invalid capability token: {name!r}")


def evaluate_degraded_mode(
    contract: DegradedModeContract,
    evidence: Mapping[str, ServiceState],
) -> ServiceState:
    """Classify a composed service without manufacturing success.

    Missing evidence is UNKNOWN.  Required unavailability makes the composed
    service unavailable; a known failure of an optional capability makes the
    service degraded.  UNKNOWN anywhere prevents a HEALTHY claim.
    """

    required_states = [evidence.get(name, ServiceState.UNKNOWN) for name in contract.required]
    optional_states = [evidence.get(name, ServiceState.UNKNOWN) for name in contract.optional]

    if ServiceState.UNAVAILABLE in required_states:
        return ServiceState.UNAVAILABLE
    if ServiceState.UNKNOWN in required_states:
        return ServiceState.UNKNOWN
    if ServiceState.DEGRADED in required_states:
        return ServiceState.DEGRADED

    if ServiceState.UNKNOWN in optional_states:
        return ServiceState.UNKNOWN
    if any(state in {ServiceState.DEGRADED, ServiceState.UNAVAILABLE} for state in optional_states):
        return ServiceState.DEGRADED

    return ServiceState.HEALTHY


def classify_partial_truth(*, succeeded: int, failed: int, unknown: int = 0) -> ServiceState:
    """Classify partition/batch truth while preserving partial failure.

    A zero-observation result is UNKNOWN rather than an invented healthy/empty
    result.  Any unknown partition prevents a stronger aggregate claim.
    """

    if min(succeeded, failed, unknown) < 0:
        raise ValueError("partition counts must be non-negative")
    if unknown:
        return ServiceState.UNKNOWN
    if failed and succeeded:
        return ServiceState.DEGRADED
    if failed:
        return ServiceState.UNAVAILABLE
    if succeeded:
        return ServiceState.HEALTHY
    return ServiceState.UNKNOWN


@dataclass(frozen=True)
class RecoveryEvidence:
    service_state: ServiceState
    expected_state_verified: Optional[bool] = None
    tenant_isolation_verified: Optional[bool] = None
    no_silent_data_loss_verified: Optional[bool] = None
    retry_quiesced: Optional[bool] = None
    customer_journey_verified: Optional[bool] = None


def classify_recovery(evidence: RecoveryEvidence) -> RecoveryState:
    """Separate service restoration from evidence-backed recovery verification."""

    checks: Sequence[Optional[bool]] = (
        evidence.expected_state_verified,
        evidence.tenant_isolation_verified,
        evidence.no_silent_data_loss_verified,
        evidence.retry_quiesced,
        evidence.customer_journey_verified,
    )

    if any(value is False for value in checks):
        return RecoveryState.FAILED
    if evidence.service_state is ServiceState.UNKNOWN:
        return RecoveryState.UNKNOWN
    if evidence.service_state is not ServiceState.HEALTHY:
        return RecoveryState.IN_PROGRESS
    if all(value is True for value in checks):
        return RecoveryState.RECOVERY_VERIFIED
    return RecoveryState.SERVICE_RESTORED


@dataclass(frozen=True)
class FailurePlan:
    """Deterministic test plan; it performs no runtime monkey-patching or I/O."""

    point: str
    failure_class: FailureClass
    fail_attempts: Tuple[int, ...]
    partial: bool = False

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.point):
            raise ValueError("failure point must be a bounded token")
        if self.failure_class is FailureClass.UNKNOWN:
            raise ValueError("failure plans must name a concrete failure class")
        if not self.fail_attempts:
            raise ValueError("failure plan must inject at least once")
        if len(set(self.fail_attempts)) != len(self.fail_attempts):
            raise ValueError("failure attempts must be unique")
        if any(attempt < 1 or attempt > 32 for attempt in self.fail_attempts):
            raise ValueError("failure attempts must be between 1 and 32")

    def failure_for(self, attempt: int) -> Optional[FailureClass]:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        return self.failure_class if attempt in self.fail_attempts else None


def validate_manifest(manifest: Mapping[str, Any]) -> Tuple[str, ...]:
    """Fail-closed audit for the machine-readable factory manifest."""

    errors = []
    if manifest.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract_version")
    if manifest.get("execution_scope") != "TEST_ONLY_NON_RUNTIME":
        errors.append("execution_scope")

    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("scenarios")
        return tuple(errors)

    seen = set()
    for index, scenario in enumerate(scenarios):
        prefix = f"scenarios[{index}]"
        if not isinstance(scenario, Mapping):
            errors.append(prefix)
            continue
        scenario_id = scenario.get("id")
        owner = scenario.get("owner")
        failure_class = scenario.get("failure_class")
        expected = scenario.get("expected_service_state")
        required_evidence = scenario.get("required_recovery_evidence")

        if not isinstance(scenario_id, str) or not _TOKEN.fullmatch(scenario_id):
            errors.append(prefix + ".id")
        elif scenario_id in seen:
            errors.append(prefix + ".duplicate_id")
        else:
            seen.add(scenario_id)

        if not isinstance(owner, str) or not owner.strip():
            errors.append(prefix + ".owner")
        if failure_class not in {item.value for item in FailureClass if item is not FailureClass.UNKNOWN}:
            errors.append(prefix + ".failure_class")
        if expected not in {item.value for item in ServiceState}:
            errors.append(prefix + ".expected_service_state")
        if not isinstance(required_evidence, list) or not required_evidence:
            errors.append(prefix + ".required_recovery_evidence")

    return tuple(errors)
