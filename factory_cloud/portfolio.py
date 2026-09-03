from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PORTFOLIO_PATH = Path(__file__).with_name("portfolio_architecture.json")
REGISTRY_PATH = Path(__file__).with_name("factories.json")


class PortfolioError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise PortfolioError(f"expected JSON object: {path}")
    return data


def load_portfolio(
    path: Path = PORTFOLIO_PATH,
    registry_path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    """Load planning metadata and fail closed on contradictory source truth.

    Portfolio metadata may describe future/unregistered factories, but every factory
    marked registered (or registered_read_only) must exist in the canonical thin
    switchboard. Conversely, every switchboard factory must have exactly one
    portfolio entry so grouping never silently drops a registered factory.
    """
    data = _load_json(path)
    registry = _load_json(registry_path)

    layer_ids = {str(item.get("id") or "") for item in data.get("layers", [])}
    gate_ids = {str(item.get("id") or "") for item in data.get("maturity_gates", [])}
    gate_ids.add("UNASSESSED")

    entries: dict[str, dict[str, Any]] = {}
    for entry in data.get("portfolio", []):
        factory_id = str(entry.get("id") or "").strip()
        if not factory_id or factory_id in entries:
            raise PortfolioError("portfolio factory ids must be unique and non-empty")
        if entry.get("layer") not in layer_ids:
            raise PortfolioError(f"unknown portfolio layer: {factory_id}")
        if entry.get("maturity") not in gate_ids:
            raise PortfolioError(f"unknown maturity gate: {factory_id}")
        source_status = str(entry.get("source_status") or "")
        if source_status not in {"registered", "registered_read_only", "unregistered"}:
            raise PortfolioError(f"invalid source_status: {factory_id}")
        entries[factory_id] = entry

    registry_ids = {
        str(factory.get("id") or "").strip()
        for factory in registry.get("factories", [])
        if str(factory.get("id") or "").strip()
    }
    mapped_registered = {
        factory_id
        for factory_id, entry in entries.items()
        if entry.get("source_status") in {"registered", "registered_read_only"}
    }

    missing = sorted(registry_ids - mapped_registered)
    phantom = sorted(mapped_registered - registry_ids)
    if missing:
        raise PortfolioError("registered factories missing portfolio mapping: " + ", ".join(missing))
    if phantom:
        raise PortfolioError("portfolio claims unverified registered factories: " + ", ".join(phantom))

    return data


def portfolio_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry["id"]): entry for entry in data.get("portfolio", [])}
