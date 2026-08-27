from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).with_name("apps.json")
ACTIVATION_CODE = "Ω"


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


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("activation_code") != ACTIVATION_CODE:
        raise RegistryError("activation_code must be Ω")
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
            continue
        mode = activation.get("mode")
        if mode not in {"repository_safe_execution", "read_only_until_source_resolved"}:
            raise RegistryError(f"unsupported activation mode for {app_id}: {mode}")


def build_queue(registry: dict[str, Any]) -> list[AppWorkItem]:
    queue: list[AppWorkItem] = []
    for app in registry.get("applications", []):
        activation = app.get("activation") or {}
        if activation.get("enabled") is not True:
            continue
        baton = app.get("baton") or {}
        queue.append(
            AppWorkItem(
                app_id=app["app_id"],
                name=app["name"],
                priority=int(activation.get("priority", 0)),
                mode=activation["mode"],
                active=str(baton.get("active") or ""),
                next_items=tuple(str(x) for x in baton.get("next", [])),
                wait_items=tuple(str(x) for x in baton.get("wait", [])),
            )
        )
    return sorted(queue, key=lambda item: (-item.priority, item.app_id))


def activation_plan(code: str, registry: dict[str, Any]) -> dict[str, Any]:
    if code != ACTIVATION_CODE:
        raise RegistryError("Factory Cloud activation requires Ω")
    queue = build_queue(registry)
    return {
        "activation_code": ACTIVATION_CODE,
        "scope": "application_development_only",
        "execution_contract": {
            "transition": "ACTIVE -> EXECUTE -> VERIFY -> DONE -> NEXT -> EXECUTE",
            "blocked_app": "freeze baton and continue with next eligible app",
            "turn_boundary": "freeze exact baton; next Ω resumes from RESUME_AT",
            "status_is_not_execution": True,
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
                "mode": item.mode,
                "active": item.active,
                "next": list(item.next_items),
                "wait": list(item.wait_items),
            }
            for item in queue
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Factory Cloud application control plane")
    parser.add_argument("code", help="activation code; must be Ω")
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
