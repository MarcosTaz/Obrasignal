import pytest

from capability_rollout import rollout_keys, runtime_enabled


def test_evidence_experiment_is_disabled_by_default_and_requires_explicit_flag():
    feature, kill = rollout_keys("EVIDENCE")
    assert feature == "OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1"
    assert kill == "OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1"
    assert runtime_enabled("EVIDENCE", environ={}) is False
    assert runtime_enabled("EVIDENCE", environ={feature: "true"}) is True


def test_evidence_kill_switch_always_wins():
    feature, kill = rollout_keys("EVIDENCE")
    assert runtime_enabled("EVIDENCE", environ={feature: "true", kill: "true"}) is False
    assert runtime_enabled("EVIDENCE", environ={feature: "true", kill: "1"}) is False


def test_invalid_rollout_configuration_fails_closed():
    feature, kill = rollout_keys("EVIDENCE")
    with pytest.raises(RuntimeError, match="invalid boolean"):
        runtime_enabled("EVIDENCE", environ={feature: "sometimes"})
    with pytest.raises(RuntimeError, match="invalid boolean"):
        runtime_enabled("EVIDENCE", environ={feature: "true", kill: "maybe"})


def test_research_capability_cannot_be_enabled_by_environment_flag_alone():
    feature, _ = rollout_keys("COMMAND")
    assert feature == "OBRASIGNAL_FEATURE_COMMAND_NEXT_BEST_ACTION"
    assert runtime_enabled("COMMAND", environ={feature: "true"}) is False


def test_enabled_capability_without_feature_flag_remains_enabled():
    assert rollout_keys("SIGNAL") == (None, None)
    assert runtime_enabled("SIGNAL", environ={}) is True
