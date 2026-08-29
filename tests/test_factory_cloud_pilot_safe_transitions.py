import pytest

from factory_cloud.pilot_safe_transitions import (
    POST_PILOT_STATES,
    PilotSafeTransitionError,
    can_enter_state,
    require_pilot_safe_for_state,
)


def test_every_customer_or_commercial_state_requires_pilot_safe():
    for state in POST_PILOT_STATES:
        assert can_enter_state(target_state=state, pilot_safe=False) is False
        with pytest.raises(PilotSafeTransitionError, match="requires PILOT_SAFE"):
            require_pilot_safe_for_state(target_state=state, pilot_safe=False)


def test_pilot_safe_allows_transition_check_but_grants_no_other_authority():
    for state in POST_PILOT_STATES:
        assert can_enter_state(target_state=state, pilot_safe=True) is True


def test_pre_customer_internal_states_are_not_blocked_by_commercial_gate():
    assert can_enter_state(target_state="SYNTHETIC_CERTIFICATION", pilot_safe=False) is True
    assert can_enter_state(target_state="SHADOW_VALIDATION", pilot_safe=False) is True
