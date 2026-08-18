"""Dashboard view helpers for explainable opportunity decisions."""
from __future__ import annotations

from decision_log import latest_decision
from decision_presentation import present_decision


def get_presented_decision(conn, source: str | None, external_id: str | None) -> dict:
    if not source or not external_id:
        return present_decision(None)
    return present_decision(latest_decision(conn, source, external_id))
