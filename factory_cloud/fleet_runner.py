from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory_cloud.factory_switchboard import REGISTRY_PATH, load_switchboard, start_packet

STATE_PATH = Path(__file__).with_name("fleet_runner_state.json")


class FleetRunnerError(RuntimeError):
    pass


def load_fleet_state(path: Path = STATE_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if state.get("command") != "D":
        raise FleetRunnerError("fleet runner command must be D")
    if state.get("status") != "ACTIVE":
        raise FleetRunnerError("fleet runner is not ACTIVE")
    cursor = state.get("cursor")
    if not isinstance(cursor, int) or cursor < 0:
        raise FleetRunnerError("fleet runner cursor must be a non-negative integer")
    return state


def _blocked_factory_ids(state: dict[str, Any]) -> set[str]:
    blocked_ids: set[str] = set()
    for item in state.get("blocked", []):
        if isinstance(item, str):
            blocked_ids.add(item)
        elif isinstance(item, dict):
            factory_id = str(item.get("factory_id") or "").strip()
            if factory_id:
                blocked_ids.add(factory_id)
    return blocked_ids


def select_next_factory(switchboard: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], int]:
    factories = list(switchboard.get("factories", []))
    if not factories:
        raise FleetRunnerError("factory registry is empty")

    blocked = _blocked_factory_ids(state)
    start = state["cursor"] % len(factories)
    for offset in range(len(factories)):
        index = (start + offset) % len(factories)
        factory = factories[index]
        if str(factory.get("id")) not in blocked:
            return factory, index
    raise FleetRunnerError("all registered factories are blocked")


def build_dispatch(
    switchboard: dict[str, Any], state: dict[str, Any], *, now: datetime | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    factory, index = select_next_factory(switchboard, state)
    packet = start_packet(str(factory["id"]), switchboard)

    updated = deepcopy(state)
    factory_count = len(switchboard["factories"])
    updated["cursor"] = (index + 1) % factory_count
    updated["last_factory_id"] = str(factory["id"])
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    updated["last_run_at"] = timestamp.isoformat().replace("+00:00", "Z")
    updated["last_material_change"] = {
        "kind": "DISPATCH_SELECTED_NO_EXECUTION_CLAIM",
        "factory_id": str(factory["id"]),
        "evidence": "registry+fleet_state",
    }
    return packet, updated


def persist_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Cloud persistent fleet runner")
    parser.add_argument("command", choices=["D"])
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    try:
        switchboard = load_switchboard(args.registry)
        state = load_fleet_state(args.state)
        packet, updated = build_dispatch(switchboard, state)
        if args.persist:
            persist_state(args.state, updated)
    except (OSError, json.JSONDecodeError, FleetRunnerError) as exc:
        parser.error(str(exc))

    print(json.dumps({"dispatch": packet, "state": updated}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
