import json
from pathlib import Path

import pytest

from resilience_factory import (
    AttemptEvidence,
    DegradedModeContract,
    FailureClass,
    FailurePlan,
    IdempotencyState,
    MutationState,
    RecoveryEvidence,
    RecoveryState,
    RetryDecision,
    RetryPolicy,
    ServiceState,
    classify_partial_truth,
    classify_recovery,
    decide_retry,
    evaluate_degraded_mode,
    validate_manifest,
)


def test_transient_uncommitted_failure_has_bounded_retry():
    policy = RetryPolicy(max_attempts=3, base_backoff_ms=100, max_backoff_ms=250)
    verdict = decide_retry(
        AttemptEvidence(
            FailureClass.TIMEOUT,
            attempt=1,
            mutation_state=MutationState.UNCOMMITTED,
        ),
        policy,
    )
    assert verdict.decision is RetryDecision.RETRY
    assert verdict.delay_ms == 100
    assert policy.delay_after(2) == 200
    assert policy.delay_after(3) == 250


def test_retry_exhaustion_stops_instead_of_storming():
    policy = RetryPolicy(max_attempts=3)
    verdict = decide_retry(AttemptEvidence(FailureClass.TIMEOUT, attempt=3), policy)
    assert verdict.decision is RetryDecision.STOP_EXHAUSTED
    assert verdict.delay_ms is None


@pytest.mark.parametrize("mutation_state", [MutationState.COMMITTED, MutationState.UNKNOWN])
def test_uncertain_or_committed_write_requires_proven_idempotency(mutation_state):
    policy = RetryPolicy(max_attempts=4)
    verdict = decide_retry(
        AttemptEvidence(
            FailureClass.TIMEOUT,
            attempt=1,
            mutation_state=mutation_state,
            idempotency=IdempotencyState.NOT_PROVEN,
        ),
        policy,
    )
    assert verdict.decision is RetryDecision.STOP_UNSAFE_REPLAY


def test_proven_idempotency_allows_bounded_replay_after_commit():
    verdict = decide_retry(
        AttemptEvidence(
            FailureClass.NOTIFICATION_DELIVERY_FAILURE,
            attempt=1,
            mutation_state=MutationState.COMMITTED,
            idempotency=IdempotencyState.PROVEN,
        ),
        RetryPolicy(max_attempts=2, base_backoff_ms=50, max_backoff_ms=50),
    )
    assert verdict.decision is RetryDecision.RETRY
    assert verdict.delay_ms == 50


def test_unknown_failure_is_never_blindly_retried():
    verdict = decide_retry(
        AttemptEvidence(FailureClass.UNKNOWN, attempt=1),
        RetryPolicy(max_attempts=5),
    )
    assert verdict.decision is RetryDecision.STOP_NON_RETRYABLE


def test_safety_violation_beats_availability():
    verdict = decide_retry(
        AttemptEvidence(
            FailureClass.TIMEOUT,
            attempt=1,
            tenant_safe=False,
            truth_preserved=True,
        ),
        RetryPolicy(),
    )
    assert verdict.decision is RetryDecision.STOP_SAFETY_VIOLATION


def test_policy_rejects_unknown_as_retryable():
    with pytest.raises(ValueError, match="UNKNOWN"):
        RetryPolicy(retryable=frozenset({FailureClass.UNKNOWN}))


def test_required_dependency_unavailable_makes_service_unavailable():
    contract = DegradedModeContract(required=("database", "auth"), optional=("notifications",))
    state = evaluate_degraded_mode(
        contract,
        {
            "database": ServiceState.UNAVAILABLE,
            "auth": ServiceState.HEALTHY,
            "notifications": ServiceState.HEALTHY,
        },
    )
    assert state is ServiceState.UNAVAILABLE


def test_optional_failure_is_degraded_not_complete_success():
    contract = DegradedModeContract(required=("radar",), optional=("notifications",))
    state = evaluate_degraded_mode(
        contract,
        {"radar": ServiceState.HEALTHY, "notifications": ServiceState.UNAVAILABLE},
    )
    assert state is ServiceState.DEGRADED


def test_missing_evidence_prevents_healthy_claim():
    contract = DegradedModeContract(required=("radar",), optional=("source_health",))
    assert evaluate_degraded_mode(contract, {"radar": ServiceState.HEALTHY}) is ServiceState.UNKNOWN


def test_all_observed_healthy_is_healthy():
    contract = DegradedModeContract(required=("database", "auth"), optional=("source_health",))
    state = evaluate_degraded_mode(
        contract,
        {
            "database": ServiceState.HEALTHY,
            "auth": ServiceState.HEALTHY,
            "source_health": ServiceState.HEALTHY,
        },
    )
    assert state is ServiceState.HEALTHY


@pytest.mark.parametrize(
    "succeeded,failed,unknown,expected",
    [
        (3, 0, 0, ServiceState.HEALTHY),
        (2, 1, 0, ServiceState.DEGRADED),
        (0, 2, 0, ServiceState.UNAVAILABLE),
        (2, 0, 1, ServiceState.UNKNOWN),
        (0, 0, 0, ServiceState.UNKNOWN),
    ],
)
def test_partial_failure_truth_never_becomes_false_complete(succeeded, failed, unknown, expected):
    assert classify_partial_truth(succeeded=succeeded, failed=failed, unknown=unknown) is expected


def test_service_response_is_not_verified_recovery():
    evidence = RecoveryEvidence(service_state=ServiceState.HEALTHY)
    assert classify_recovery(evidence) is RecoveryState.SERVICE_RESTORED


def test_verified_recovery_requires_all_safety_and_customer_evidence():
    evidence = RecoveryEvidence(
        service_state=ServiceState.HEALTHY,
        expected_state_verified=True,
        tenant_isolation_verified=True,
        no_silent_data_loss_verified=True,
        retry_quiesced=True,
        customer_journey_verified=True,
    )
    assert classify_recovery(evidence) is RecoveryState.RECOVERY_VERIFIED


def test_failed_recovery_check_is_not_hidden_by_healthy_service():
    evidence = RecoveryEvidence(
        service_state=ServiceState.HEALTHY,
        expected_state_verified=True,
        tenant_isolation_verified=False,
        no_silent_data_loss_verified=True,
        retry_quiesced=True,
        customer_journey_verified=True,
    )
    assert classify_recovery(evidence) is RecoveryState.FAILED


def test_unknown_service_state_stays_unknown_recovery():
    assert classify_recovery(RecoveryEvidence(ServiceState.UNKNOWN)) is RecoveryState.UNKNOWN


def test_degraded_service_is_recovery_in_progress():
    assert classify_recovery(RecoveryEvidence(ServiceState.DEGRADED)) is RecoveryState.IN_PROGRESS


def test_failure_plan_is_deterministic_and_side_effect_free():
    plan = FailurePlan("source.fetch", FailureClass.TIMEOUT, (1, 3))
    assert plan.failure_for(1) is FailureClass.TIMEOUT
    assert plan.failure_for(2) is None
    assert plan.failure_for(3) is FailureClass.TIMEOUT


def test_failure_plan_rejects_unknown_or_duplicate_attempts():
    with pytest.raises(ValueError):
        FailurePlan("source.fetch", FailureClass.UNKNOWN, (1,))
    with pytest.raises(ValueError):
        FailurePlan("source.fetch", FailureClass.TIMEOUT, (1, 1))


def test_repository_resilience_manifest_is_fail_closed_and_valid():
    manifest = json.loads(Path("resilience_manifest.json").read_text(encoding="utf-8"))
    assert validate_manifest(manifest) == ()


def test_manifest_drift_is_detected_without_guessing():
    manifest = json.loads(Path("resilience_manifest.json").read_text(encoding="utf-8"))
    manifest["execution_scope"] = "PRODUCTION"
    manifest["scenarios"][0]["failure_class"] = "MYSTERY"
    errors = validate_manifest(manifest)
    assert "execution_scope" in errors
    assert "scenarios[0].failure_class" in errors
