from __future__ import annotations

import copy

import pytest

from operability_acceptance import (
    DEFAULT_OBSERVATION,
    OperabilityContractError,
    assert_current_main,
    evaluate,
    load_observation,
    validate_observation,
)


EXPECTED_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"


def _observation():
    return load_observation(DEFAULT_OBSERVATION)


def _all_ready():
    observation = copy.deepcopy(_observation())
    observation["probes"]["liveness"]["state"] = "UP"
    observation["probes"]["database"]["state"] = "READY"
    observation["probes"]["worker"]["state"] = "READY"
    for dependency in observation["probes"]["dependencies"]:
        dependency["state"] = "READY"
    correlation = observation["probes"]["support_correlation"]
    correlation["state"] = "READY"
    correlation["safety"] = {
        "opaque_identifier": True,
        "excludes_bearer_jwt_secrets": True,
        "excludes_profile_notes_private_payloads": True,
        "excludes_raw_account_identifier": True,
    }
    return observation


def test_current_canonical_observation_is_no_go_despite_liveness_up():
    result = evaluate(_observation())
    assert result.verdict == "NO_GO"
    assert "DATABASE_UNKNOWN" in result.reasons
    assert "WORKER_UNKNOWN" in result.reasons
    assert "DEPENDENCY_critical_upstreams_UNKNOWN" in result.reasons
    assert "SUPPORT_CORRELATION_UNKNOWN" in result.reasons


@pytest.mark.parametrize("state", ["DEGRADED", "UNAVAILABLE", "UNKNOWN"])
def test_database_not_ready_fails_closed(state):
    observation = _all_ready()
    observation["probes"]["database"]["state"] = state
    result = evaluate(observation)
    assert result.verdict == "NO_GO"
    assert f"DATABASE_{state}" in result.reasons


@pytest.mark.parametrize("state", ["DEGRADED", "STALLED", "UNAVAILABLE", "UNKNOWN"])
def test_worker_not_ready_fails_closed(state):
    observation = _all_ready()
    observation["probes"]["worker"]["state"] = state
    result = evaluate(observation)
    assert result.verdict == "NO_GO"
    assert f"WORKER_{state}" in result.reasons


@pytest.mark.parametrize("state", ["DEGRADED", "UNAVAILABLE", "UNKNOWN"])
def test_critical_dependency_not_ready_fails_closed(state):
    observation = _all_ready()
    observation["probes"]["dependencies"][0]["state"] = state
    result = evaluate(observation)
    assert result.verdict == "NO_GO"
    assert f"DEPENDENCY_critical_upstreams_{state}" in result.reasons


def test_liveness_up_alone_never_implies_readiness():
    observation = _all_ready()
    observation["probes"]["database"]["state"] = "UNKNOWN"
    assert observation["probes"]["liveness"]["state"] == "UP"
    assert evaluate(observation).verdict == "NO_GO"


def test_unknown_liveness_fails_closed():
    observation = _all_ready()
    observation["probes"]["liveness"]["state"] = "UNKNOWN"
    result = evaluate(observation)
    assert result.verdict == "NO_GO"
    assert "LIVENESS_UNKNOWN" in result.reasons


def test_support_correlation_unknown_or_unsafe_fails_closed():
    for state in ("UNKNOWN", "UNSAFE"):
        observation = _all_ready()
        observation["probes"]["support_correlation"]["state"] = state
        result = evaluate(observation)
        assert result.verdict == "NO_GO"
        assert f"SUPPORT_CORRELATION_{state}" in result.reasons


def test_support_correlation_cannot_claim_ready_without_all_privacy_guards():
    observation = _all_ready()
    observation["probes"]["support_correlation"]["safety"][
        "excludes_raw_account_identifier"
    ] = False
    with pytest.raises(OperabilityContractError, match="privacy-safe evidence"):
        validate_observation(observation)


def test_only_complete_ready_observation_can_pass_operability_acceptance():
    result = evaluate(_all_ready())
    assert result.verdict == "READY"
    assert result.reasons == ()


def test_main_drift_invalidates_operability_observation():
    assert_current_main(_observation(), EXPECTED_MAIN)
    with pytest.raises(OperabilityContractError, match="observation is stale"):
        assert_current_main(_observation(), "f" * 40)
