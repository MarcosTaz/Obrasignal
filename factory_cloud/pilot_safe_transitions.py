from __future__ import annotations

POST_PILOT_STATES = (
    "CONTROLLED_REAL_PILOT",
    "PILOT_VALIDATED",
    "COMMERCIAL_READY",
    "MARKET_VALIDATED",
    "REPEATABLE",
    "SCALE_READY",
)


class PilotSafeTransitionError(RuntimeError):
    pass


def require_pilot_safe_for_state(*, target_state: str, pilot_safe: bool) -> None:
    """Block every customer/commercial state until pre-customer certification passes."""
    if target_state in POST_PILOT_STATES and not pilot_safe:
        raise PilotSafeTransitionError(
            f"{target_state} requires PILOT_SAFE pre-customer certification"
        )


def can_enter_state(*, target_state: str, pilot_safe: bool) -> bool:
    try:
        require_pilot_safe_for_state(target_state=target_state, pilot_safe=pilot_safe)
    except PilotSafeTransitionError:
        return False
    return True
