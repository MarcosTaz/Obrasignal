from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INVENTORY_PATH = Path(__file__).with_name("capability_inventory.json")
ALLOWED_STATES = {
    "VERTICAL_ONLY",
    "CANDIDATE_SHARED",
    "SHARED_CONTRACT_PROPOSED",
    "SHARED_VERIFIED",
    "SHARED_CORE",
}
ALLOWED_LAYERS = {"shared-platform", "assurance-kernel"}


class CapabilityInventoryError(RuntimeError):
    pass


def load_capability_inventory(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise CapabilityInventoryError("capability inventory must be a JSON object")

    seen: set[str] = set()
    for capability in data.get("capabilities", []):
        capability_id = str(capability.get("id") or "").strip()
        if not capability_id or capability_id in seen:
            raise CapabilityInventoryError("capability ids must be unique and non-empty")
        seen.add(capability_id)
        if capability.get("layer") not in ALLOWED_LAYERS:
            raise CapabilityInventoryError(f"invalid capability layer: {capability_id}")
        state = str(capability.get("state") or "")
        if state not in ALLOWED_STATES:
            raise CapabilityInventoryError(f"invalid promotion state: {capability_id}")
        if not str(capability.get("source_app") or "").strip():
            raise CapabilityInventoryError(f"source_app required: {capability_id}")
        evidence_paths = capability.get("evidence_paths")
        if not isinstance(evidence_paths, list):
            raise CapabilityInventoryError(f"evidence_paths must be a list: {capability_id}")
        if not str(capability.get("next_proof") or "").strip():
            raise CapabilityInventoryError(f"next_proof required: {capability_id}")

        consumers = capability.get("verified_consumers", [])
        if not isinstance(consumers, list) or any(not isinstance(item, str) or not item.strip() for item in consumers):
            raise CapabilityInventoryError(f"verified_consumers must be a list of ids: {capability_id}")
        if len(set(consumers)) != len(consumers):
            raise CapabilityInventoryError(f"verified_consumers must be unique: {capability_id}")

        if state in {"SHARED_VERIFIED", "SHARED_CORE"}:
            if not evidence_paths:
                raise CapabilityInventoryError(
                    f"verified/shared core capability requires evidence paths: {capability_id}"
                )
            if len(consumers) < 2:
                raise CapabilityInventoryError(
                    f"verified/shared core capability requires at least two consumers: {capability_id}"
                )
        if state == "SHARED_CORE" and not str(capability.get("owner") or "").strip():
            raise CapabilityInventoryError(f"shared core capability requires owner: {capability_id}")
    return data


def capability_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in data.get("capabilities", [])}
