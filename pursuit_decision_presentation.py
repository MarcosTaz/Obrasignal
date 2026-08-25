"""Small contextual presentation contract for pursuit decisions."""
from __future__ import annotations

DECISION_ACTIONS = (
    {"value": "PURSUE", "label": "PURSUE"},
    {"value": "HOLD", "label": "HOLD"},
    {"value": "NO_BID", "label": "NO-BID"},
    {"value": "NEEDS_INFO", "label": "NEEDS INFO"},
)


def present_pursuit_decision(current: dict | None, history: list[dict] | None = None) -> dict:
    return {
        "title": "YOUR DECISION",
        "actions": [dict(item) for item in DECISION_ACTIONS],
        "current": current,
        "history": list(history or []),
    }
