from capability_registry import (
    CAPABILITIES,
    capability,
    dependency_cycles,
    enabled_capabilities,
)


def test_registry_has_no_capability_dependency_cycles():
    assert dependency_cycles() == ()


def test_signal_is_enabled_but_future_engines_are_not_silently_promoted():
    assert enabled_capabilities() == ("SIGNAL",)
    assert capability("SHADOW").state == "RESEARCH"
    assert capability("ACTION").state == "RESEARCH"
    assert capability("MOBILIZE").state == "RESEARCH"
    assert capability("CONTRACT_EXPIRY").state == "RESEARCH"
    assert capability("CONTRACT_EXPIRY").feature_flag == "contract_expiry_signals_v0"
    assert capability("CONTRACT_EXPIRY").dependencies == ("SIGNAL",)


def test_risky_or_experimental_capabilities_have_kill_switchable_flags():
    for spec in CAPABILITIES.values():
        if spec.kill_switch_required:
            assert spec.feature_flag
        if spec.state in {"EXPERIMENT", "PILOT"}:
            assert spec.feature_flag


def test_private_data_ownership_and_failure_mode_are_declared():
    for spec in CAPABILITIES.values():
        assert spec.private_data_owner
        assert spec.failure_mode == "degrade_without_platform_failure"


def test_action_depends_on_command_contract_not_unrelated_private_storage():
    action = capability("ACTION")
    assert action.dependencies == ("COMMAND",)
    assert "authorized_action.v1-draft" in action.contract_versions


def test_signal_contract_is_explicit_and_event_publishing_is_decoupled():
    signal = capability("SIGNAL")
    assert signal.contract_versions == ("signal.v1",)
    assert "opportunity.updated" in signal.publishes_events
