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
from factory_cloud.portfolio_priority import PortfolioPriorityError, priority_for_app

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
    if not isinstance(allowlisted, list) or not allowlisted or any(not isinstance(item, str) or not item.strip() for item in allowlisted):
        raise RegistryError(f"execution_adapter allowlisted_tasks must be explicit: {app_id}")
    if len(set(allowlisted)) != len(allowlisted):
        raise RegistryError(f"execution_adapter allowlisted_tasks must be unique: {app_id}")
    if not isinstance(task_contracts, dict):
        raise RegistryError(f"task_capabilities must be an object: {app_id}")
    if set(task_contracts) != set(allowlisted):
        raise RegistryError(f"every allowlisted task must have exactly one capability contract: {app_id}")

    try:
        declared = parse_capabilities(adapter.get("capabilities"), require_explicit=True)
        for task in allowlisted:
            required = parse_capabilities(task_contracts.get(task), require_explicit=True)
            require_capabilities(declared, required)
    except CapabilityContractError as exc:
        raise RegistryError(f"invalid capability contract for {app_id}: {exc}") from exc

    mutation_caps = {Capability.CREATE_BRANCH, Capability.WRITE_FILES, Capability.CREATE_PR}
    declared_mutation = bool(declared & mutation_caps)
    if bool(adapter.get("repository_mutation_capability")) != declared_mutation:
        raise RegistryError(f"repository_mutation_capability disagrees with declared capabilities: {app_id}")


def _validate_portfolio_priority(app: dict[str, Any]) -> None:
    try:
        priority_for_app(app)
    except PortfolioPriorityError as exc:
        raise RegistryError(f"invalid portfolio priority for {app['app_id']}: {exc}") from exc


def _validate_runtime_wait_app(app: dict[str, Any]) -> None:
    app_id = app["app_id"]
    activation = app.get("activation") or {}
    if activation.get("enabled") is not False or activation.get("mode") != "runtime_provisioning_wait":
        raise RegistryError(f"runtime wait app must be disabled and explicit: {app_id}")
    if not str(app.get("development_state") or "").endswith("RUNTIME_PROVISIONING_WAIT"):
        raise RegistryError(f"runtime wait development_state required: {app_id}")
    baton = app.get("baton") or {}
    if str(baton.get("active") or "") != "runtime:provision":
        raise RegistryError(f"runtime wait baton must remain on runtime:provision: {app_id}")
    _validate_execution_source(app, "repository_safe_execution")
    _validate_capability_contract(app, "repository_safe_execution")
    _validate_portfolio_priority(app)


def _validate_assisted_business_runtime_wait_app(app: dict[str, Any]) -> None:
    """Validate a disabled app that can progress business-side while host runtime remains gated."""
    app_id = app["app_id"]
    activation = app.get("activation") or {}
    if activation.get("enabled") is not False or activation.get("mode") != "assisted_business_runtime_wait":
        raise RegistryError(f"assisted business runtime wait app must be disabled and explicit: {app_id}")
    if not str(app.get("development_state") or "").endswith("RUNTIME_PROVISIONING_WAIT"):
        raise RegistryError(f"assisted business runtime wait development_state required: {app_id}")
    baton = app.get("baton") or {}
    if str(baton.get("active") or "") != "business:real-case":
        raise RegistryError(f"assisted business runtime wait baton must remain on business:real-case: {app_id}")
    wait_items = tuple(str(item) for item in baton.get("wait", []))
    if not any("runtime workspace provisioning" in item for item in wait_items):
        raise RegistryError(f"assisted business runtime wait must preserve runtime provisioning gate: {app_id}")
    _validate_execution_source(app, "repository_safe_execution")
    _validate_capability_contract(app, "repository_safe_execution")
    _validate_portfolio_priority(app)


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("activation_code") != ACTIVATION_CODE:
        raise RegistryError("activation_code must be D")
    if registry.get("registry_scope") != "application_development_only":
        raise RegistryError("registry scope must remain application_development_only")

    rules = registry.get("rules") or {}
    required_true = (
        "exclude_research_factories",
        "unknown_source_is_not_absent",
        "no_automatic_merge",
        "no_automatic_deploy",
        "no_production_mutation",
        "independent_trust_boundaries",
        "no_shared_production_authority",
        "metadata_only_persistence",
    )
    for key in required_true:
        if rules.get(key) is not True:
            raise RegistryError(f"safety rule must stay true: {key}")
    if rules.get("include_only_kind") != "application":
        raise RegistryError("only kind=application may enter Factory Cloud")

    seen: set[str] = set()
    for app in registry.get("applications", []):
        app_id = app.get("app_id")
        if not app_id or app_id in seen:
            raise RegistryError("application ids must be unique and non-empty")
        seen.add(app_id)
        if app.get("kind") != "application":
            raise RegistryError(f"non-application registered: {app_id}")
        if not str(app.get("mission") or "").strip():
            raise RegistryError(f"application mission required: {app_id}")
        activation = app.get("activation") or {}
        if activation.get("enabled") is not True:
            disabled_mode = activation.get("mode")
            if disabled_mode == "runtime_provisioning_wait":
                _validate_runtime_wait_app(app)
            elif disabled_mode == "assisted_business_runtime_wait":
                _validate_assisted_business_runtime_wait_app(app)
            continue
        mode = activation.get("mode")
        if mode not in {"repository_safe_execution", "read_only_until_source_resolved"}:
            raise RegistryError(f"unsupported activation mode for {app_id}: {mode}")
        _validate_execution_source(app, mode)
        _validate_capability_contract(app, mode)
        _validate_portfolio_priority(app)


def build_queue(registry: dict[str, Any]) -> list[AppWorkItem]:
    queue: list[AppWorkItem] = []
    for app in registry.get("applications", []):
        activation = app.get("activation") or {}
        if activation.get("enabled") is not True:
            continue
        baton = app.get("baton") or {}
        effective_priority = priority_for_app(app).score
        queue.append(
            AppWorkItem(
                app_id=app["app_id"],
                name=app["name"],
                priority=effective_priority,
                mode=activation["mode"],
                active=str(baton.get("active") or ""),
                next_items=tuple(str(x) for x in baton.get("next", [])),
                wait_items=tuple(str(x) for x in baton.get("wait", [])),
            )
        )
    return sorted(queue, key=lambda item: (-item.priority, item.app_id))


def activation_plan(code: str, registry: dict[str, Any]) -> dict[str, Any]:
    if code != ACTIVATION_CODE:
        raise RegistryError("Factory Cloud activation requires D")
    queue = build_queue(registry)
    app_by_id = {app["app_id"]: app for app in registry.get("applications", [])}
    return {
        "activation_code": ACTIVATION_CODE,
        "scope": "application_development_only",
        "execution_contract": {
            "transition": "ACTIVE -> EXECUTE -> VERIFY -> DONE -> NEXT -> EXECUTE",
            "blocked_app": "freeze baton and continue with next eligible app",
            "turn_boundary": "freeze exact baton; next execution slice resumes from RESUME_AT",
            "status_is_not_execution": True,
            "priority_is_not_authority": True,
        },
        "safety": {
            "automatic_merge": False,
            "automatic_deploy": False,
            "production_mutation": False,
            "cross_app_secret_or_data_authority": False,
            "shared_production_authority": False,
            "persistent_state_scope": "metadata_only",
        },
        "queue": [
            {
                "app_id": item.app_id,
                "name": item.name,
                "priority": item.priority,
                "portfolio_priority": dict(app_by_id[item.app_id].get("portfolio_priority") or {}),
                "mode": item.mode,
                "active": item.active,
                "next": list(item.next_items),
                "wait": list(item.wait_items),
                "adapter_capabilities": list((app_by_id[item.app_id].get("execution_adapter") or {}).get("capabilities") or []),
            }
            for item in queue
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Factory Cloud application control plane")
    parser.add_argument("code", help="activation code; must be D")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = parser.parse_args()
    try:
        plan = activation_plan(args.code, load_registry(args.registry))
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        parser.error(str(exc))
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
