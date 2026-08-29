from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from factory_cloud.portfolio import PortfolioError, load_portfolio, portfolio_index

REGISTRY_PATH = Path(__file__).with_name("factories.json")
PORTFOLIO_PATH = Path(__file__).with_name("portfolio_architecture.json")


class SwitchboardError(RuntimeError):
    pass


def load_switchboard(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("scope") != "switchboard_only":
        raise SwitchboardError("factory registry must remain switchboard_only")
    ids: set[str] = set()
    for factory in data.get("factories", []):
        factory_id = str(factory.get("id") or "").strip()
        if not factory_id or factory_id in ids:
            raise SwitchboardError("factory ids must be unique and non-empty")
        ids.add(factory_id)
        if not str(factory.get("name") or "").strip():
            raise SwitchboardError(f"factory name required: {factory_id}")
        if not str(factory.get("target") or "").strip():
            raise SwitchboardError(f"factory target required: {factory_id}")
    return data


def start_packet(factory_id: str, switchboard: dict[str, Any]) -> dict[str, str]:
    for factory in switchboard.get("factories", []):
        if factory.get("id") != factory_id:
            continue
        signal = str(factory.get("signal") or switchboard.get("default_signal") or "X")
        return {
            "factory_id": factory_id,
            "name": str(factory["name"]),
            "target": str(factory["target"]),
            "signal": signal,
            "payload": (
                f"{signal} — RESUME THE EXISTING FACTORY. DO NOT RESTART. "
                "CONTINUE AUTONOMOUSLY WITH MAXIMUM SAFE AUTONOMY. "
                "A TURN OR TECHNICAL WINDOW END IS NOT A STOP CONDITION. "
                "FREEZE THE EXACT BATON AND RESUME THE NEXT EXECUTABLE ACTION UNTIL REAL COMPLETION OR A TRUE EXTERNAL BLOCKER."
            ),
        }
    raise SwitchboardError(f"unknown factory: {factory_id}")


def list_switches(switchboard: dict[str, Any]) -> list[dict[str, str]]:
    default_signal = str(switchboard.get("default_signal") or "X")
    return [
        {
            "factory_id": str(factory["id"]),
            "name": str(factory["name"]),
            "target": str(factory["target"]),
            "signal": str(factory.get("signal") or default_signal),
        }
        for factory in switchboard.get("factories", [])
    ]


def list_portfolio_switches(
    switchboard: dict[str, Any],
    portfolio: dict[str, Any],
) -> list[dict[str, str]]:
    """Return registered switches enriched with non-authoritative planning metadata.

    This does not change dispatch authority. It only exposes hierarchy/family/maturity
    already validated against the canonical switchboard source truth.
    """
    metadata = portfolio_index(portfolio)
    default_signal = str(switchboard.get("default_signal") or "X")
    rows: list[dict[str, str]] = []
    for factory in switchboard.get("factories", []):
        factory_id = str(factory["id"])
        entry = metadata.get(factory_id)
        if entry is None:
            raise SwitchboardError(f"portfolio metadata missing: {factory_id}")
        rows.append(
            {
                "factory_id": factory_id,
                "name": str(factory["name"]),
                "target": str(factory["target"]),
                "signal": str(factory.get("signal") or default_signal),
                "layer": str(entry["layer"]),
                "family": str(entry["family"]),
                "maturity": str(entry["maturity"]),
                "source_status": str(entry["source_status"]),
            }
        )
    return rows


def grouped_portfolio_switches(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row["layer"], []).append(row)
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Cloud thin switchboard")
    parser.add_argument("factory_id", nargs="?", help="factory switch to turn on")
    parser.add_argument("--list", action="store_true", dest="list_all")
    parser.add_argument("--portfolio", action="store_true", dest="portfolio_view")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--portfolio-file", type=Path, default=PORTFOLIO_PATH)
    args = parser.parse_args()

    try:
        switchboard = load_switchboard(args.registry)
        result: Any
        if args.portfolio_view:
            portfolio = load_portfolio(args.portfolio_file, args.registry)
            result = grouped_portfolio_switches(list_portfolio_switches(switchboard, portfolio))
        elif args.list_all:
            result = list_switches(switchboard)
        elif args.factory_id:
            result = start_packet(args.factory_id, switchboard)
        else:
            parser.error("provide factory_id, --list or --portfolio")
    except (OSError, json.JSONDecodeError, SwitchboardError, PortfolioError) as exc:
        parser.error(str(exc))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
