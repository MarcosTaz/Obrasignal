from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory_cloud.capabilities import (
    Capability,
    CapabilityContractError,
    parse_capabilities,
    require_capabilities,
)

REGISTRY_PATH = Path(__file__).with_name("apps.json")
ACTIVATION_CODE = "D"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppWorkItem:
    app_id: str
    name: str
    priority: int
    mode: str
    active: str
    next_items: tuple[str, ...]
    wait_items: tuple[str, ...]


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    validate_registry(registry)
    return registry


def _validate_execution_source(app: dict[str, Any], mode: str) -> None:
    execution = app.get("execution_source")
    if execution is None:
        return
    app_id = app["app_id"]
    if mode != "repository_safe_execution":
        raise RegistryError(f"execution_source requires repository_safe_execution: {app_id}")
    if not isinstance(execution, dict):
        raise RegistryError(f"execution_source must be an object: {app_id}")
    if execution.get("provider") != "github":
        raise RegistryError(f"unsupported execution_source provider: {app_id}")
    repository = str(execution.get("repository") or "").strip()
    branch = str(execution.get("branch") or "").strip()
    head = str(execution.get("head") or "").strip()
    if not repository or not branch or not _SHA_RE.fullmatch(head):
        raise RegistryError(f"execution_source must have repository, branch and exact SHA: {app_id}")
    if execution.get("verified") is not True:
        raise RegistryError(f"execution_source must be explicitly verified before activation: {app_id}")
    canonical = app.get("source_truth") or {}
    canonical_repo = str(canonical.get("repository") or canonical.get("canonical_repository") or "").strip()
    if not canonical_repo or repository != canonical_repo:
        raise RegistryError(f"execution_source repository must match canonical repository: {app_id}")


def _validate_capability_contract(app: dict[str, Any], mode: str) -> None:
    app_id = app["app_id"]
    adapter = app.get("execution_adapter")
    task_contracts = app.get("task_capabilities")

    if mode != "repository_safe_execution":
        if adapter is not None or task_contracts is not None:
            raise RegistryError(f"read-only app cannot declare repository execution capabilities: {app_id}")
        return

    if not isinstance(adapter, dict) or adapter.get("configured") is not True:
        raise RegistryError(f"repository-safe app requires an explicit configured execution_adapter: {app_id}")
    allowlisted = adapter.get("allowlisted_tasks")
    declared = adapter.get("capabilities")
    if not isinstance(allowlisted, list) or not allowlisted or not all(isinstance(task, str) and task.strip() for task in allowlisted):
        raise RegistryError(f"execution_adapter requires non-empty allowlisted_tasks: {app_id}")
    if not isinstance(declared, list) or not declared:
        raise RegistryError(f"execution_adapter requires explicit capabilities: {app_id}")
    try:
        declared_capabilities = parse_capabilities(declared)
        require_capabilities(declared_capabilities)
    except (CapabilityContractError, ValueError) as exc:
        raise RegistryError(f"unsafe execution_adapter capability contract: {app_id}: {exc}") from exc
    if adapter.get("repository_mutation_capability") is not False:
        raise RegistryError(f"repository mutation authority must stay false in this control plane: {app_id}")
    if not isinstance(task_contracts, dict):
        raise RegistryError(f"repository-safe app requires task_capabilities: {app_id}")
    if set(task_contracts) != set(allowlisted):
        raise RegistryError(f"task_capabilities must exactly cover allowlisted_tasks: {app_id}")
    for task, capabilities in task_contracts.items():
        if not isinstance(capabilities, list):
            raise RegistryError(f"task capability contract must be a list: {app_id}/{task}")
        try:
            required = parse_capabilities(capabilities)
            require_capabilities(required)
        except (CapabilityContractError, ValueError) as exc:
            raise RegistryError(f"unsafe task capability contract: {app_id}/{task}: {exc}") from exc
        if not required.issubset(declared_capabilities):
            raise RegistryError(f"task exceeds adapter capability declaration: {app_id}/{task}")


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("registry_scope") != "application_development_only":
        raise RegistryError("Factory Cloud registry must remain application-development-only")
    if registry.get("activation_code") != ACTIVATION_CODE:
        raise RegistryError("Factory Cloud activation code mismatch")
    rules = registry.get("rules") or {}
    if rules.get("include_only_kind") != "application" or rules.get("exclude_research_factories") is not True:
        raise RegistryError("Factory Cloud scope rules are not strict enough")
    if rules.get("no_automatic_merge") is not True or rules.get("no_automatic_deploy") is not True or rules.get("no_production_mutation") is not True:
        raise RegistryError("Factory Cloud safety rules are not strict enough")
    if rules.get("independent_trust_boundaries") is not True or rules.get("no_shared_production_authority") is not True:
        raise RegistryError("Factory Cloud trust-boundary rules are not strict enough")

    seen: set[str] = set()
    for app in registry.get("applications", []):
        app_id = str(app.get("app_id") or "").strip()
        if not app_id or app_id in seen:
            raise RegistryError(f"duplicate or missing app_id: {app_id}")
        seen.add(app_id)
        if app.get("kind") != "application":
            raise RegistryError(f"non-application registered in Factory Cloud: {app_id}")
        activation = app.get("activation") or {}
        mode = activation.get("mode")
        if mode not in {"repository_safe_execution", "read_only_until_source_resolved"}:
            raise RegistryError(f"unsupported activation mode: {app_id}")
        _validate_execution_source(app, mode)
        _validate_capability_contract(app, mode)


def build_queue(registry: dict[str, Any]) -> list[AppWorkItem]:
    items: list[AppWorkItem] = []
    for app in registry.get("applications", []):
        activation = app.get("activation") or {}
        if activation.get("enabled") is not True:
            continue
        baton = app.get("baton") or {}
        items.append(
            AppWorkItem(
                app_id=app["app_id"],
                name=app["name"],
                priority=int(activation.get("priority", 0)),
                mode=str(activation["mode"]),
                active=str(baton.get("active") or ""),
                next_items=tuple(str(item) for item in baton.get("next", [])),
                wait_items=tuple(str(item) for item in baton.get("wait", [])),
            )
        )
    return sorted(items, key=lambda item: (-item.priority, item.app_id))


def activation_plan(code: str, registry: dict[str, Any]) -> dict[str, Any]:
    if code != ACTIVATION_CODE:
        raise RegistryError(f"Factory Cloud activation requires {ACTIVATION_CODE}")
    validate_registry(registry)
    queue = build_queue(registry)
    return {
        "activation_code": ACTIVATION_CODE,
        "scope": registry["registry_scope"],
        "queue": [
            {
                "app_id": item.app_id,
                "name": item.name,
                "priority": item.priority,
                "mode": item.mode,
                "active": item.active,
                "next": list(item.next_items),
                "wait": list(item.wait_items),
                "adapter_capabilities": list(
                    (next(app for app in registry["applications"] if app["app_id"] == item.app_id).get("execution_adapter") or {}).get("capabilities", [])
                ),
            }
            for item in queue
        ],
        "safety": {
            "automatic_merge": False,
            "automatic_deploy": False,
            "production_mutation": False,
            "cross_app_secret_or_data_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Cloud application-development control plane")
    parser.add_argument("code", help=f"activation code; must be {ACTIVATION_CODE}")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = parser.parse_args()
    try:
        registry = load_registry(args.registry)
        plan = activation_plan(args.code, registry)
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        parser.error(str(exc))
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
