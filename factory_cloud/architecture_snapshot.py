from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from factory_cloud.capability_inventory import (
    INVENTORY_PATH,
    CapabilityInventoryError,
    load_capability_inventory,
)
from factory_cloud.factory_switchboard import (
    PORTFOLIO_PATH,
    REGISTRY_PATH,
    SwitchboardError,
    grouped_portfolio_switches,
    list_portfolio_switches,
    load_switchboard,
)
from factory_cloud.portfolio import PortfolioError, load_portfolio
from factory_cloud.promotion_queue import build_promotion_queue


def build_architecture_snapshot(
    registry_path: Path = REGISTRY_PATH,
    portfolio_path: Path = PORTFOLIO_PATH,
    inventory_path: Path = INVENTORY_PATH,
) -> dict[str, Any]:
    switchboard = load_switchboard(registry_path)
    portfolio = load_portfolio(portfolio_path, registry_path)
    capabilities = load_capability_inventory(inventory_path)
    rows = list_portfolio_switches(switchboard, portfolio)

    capability_groups: dict[str, list[dict[str, Any]]] = {}
    for capability in capabilities.get("capabilities", []):
        capability_groups.setdefault(str(capability["layer"]), []).append(dict(capability))

    promotion_queue = [
        asdict(item)
        for item in build_promotion_queue(switchboard=switchboard, portfolio=portfolio)
    ]

    return {
        "schema_version": 2,
        "authority": {
            "source": "planning_and_switchboard_metadata_only",
            "grants_repository_write": False,
            "grants_production_write": False,
            "grants_cross_app_data_access": False,
            "grants_merge": False,
        },
        "layers": portfolio.get("layers", []),
        "maturity_gates": portfolio.get("maturity_gates", []),
        "factories_by_layer": grouped_portfolio_switches(rows),
        "capabilities_by_layer": capability_groups,
        "scheduling_priority": portfolio.get("scheduling_priority", []),
        "app_promotion_queue": promotion_queue,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validated Factory Cloud portfolio architecture snapshot")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--portfolio", type=Path, default=PORTFOLIO_PATH)
    parser.add_argument("--capabilities", type=Path, default=INVENTORY_PATH)
    args = parser.parse_args()
    try:
        result = build_architecture_snapshot(args.registry, args.portfolio, args.capabilities)
    except (OSError, json.JSONDecodeError, SwitchboardError, PortfolioError, CapabilityInventoryError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
