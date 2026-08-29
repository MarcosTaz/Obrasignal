from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PilotContractError(RuntimeError):
    pass


def load_pilot_contract(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("mode") != "assisted":
        raise PilotContractError("pilot mode must be assisted")
    if payload.get("production_authority") is not False:
        raise PilotContractError("pilot contract must not grant production authority")
    for field in ("vertical", "wedge"):
        if not str(payload.get(field) or "").strip():
            raise PilotContractError(f"{field} required")
    for field in ("required_inputs", "outputs", "fail_closed", "pilot_exit_criteria"):
        value = payload.get(field)
        if not isinstance(value, list) or not value or any(not str(item).strip() for item in value):
            raise PilotContractError(f"{field} must be a non-empty list")
    pricing = payload.get("pricing") or {}
    required_pricing = ("status", "currency", "audit_fee_min", "audit_fee_max", "success_fee_percent_min", "success_fee_percent_max")
    if any(key not in pricing for key in required_pricing):
        raise PilotContractError("pricing contract incomplete")
    if pricing["status"] not in {"HYPOTHESIS", "VALIDATED"}:
        raise PilotContractError("pricing status must be HYPOTHESIS or VALIDATED")
    if pricing["audit_fee_min"] < 0 or pricing["audit_fee_max"] < pricing["audit_fee_min"]:
        raise PilotContractError("invalid audit fee range")
    if not 0 <= pricing["success_fee_percent_min"] <= pricing["success_fee_percent_max"] <= 100:
        raise PilotContractError("invalid success fee range")
    return payload
