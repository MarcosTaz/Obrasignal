from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factory_cloud.control_plane import REGISTRY_PATH, load_registry
from factory_cloud.runtime_provisioning import RuntimeProvisioningCheck, inspect_runtime


class RuntimeGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeGateDecision:
    app_id: str
    eligible: bool
    reason: str
    check: RuntimeProvisioningCheck


def assess_runtime_gate(app: dict[str, Any], *, repository_root: str | Path = ".") -> RuntimeGateDecision:
    app_id = str(app.get("app_id") or "").strip()
    if not app_id:
        raise RuntimeGateError("app_id is required")
    activation = app.get("activation") or {}
    if activation.get("enabled") is True:
        raise RuntimeGateError("runtime gate is only for disabled provisioning-wait applications")
    if activation.get("mode") != "runtime_provisioning_wait":
        raise RuntimeGateError("application is not in runtime_provisioning_wait")

    execution = app.get("execution_source") or {}
    if execution.get("verified") is not True:
        raise RuntimeGateError("verified execution source required")
    expected_head = str(execution.get("head") or "").strip()
    adapter = app.get("execution_adapter") or {}
    config_path = str(adapter.get("config_path") or "").strip()
    if not config_path:
        raise RuntimeGateError("execution adapter config_path required")

    check = inspect_runtime(
        Path(repository_root) / config_path,
        expected_app_id=app_id,
        expected_head=expected_head,
    )
    if not check.ready:
        return RuntimeGateDecision(app_id, False, "runtime_not_provisioned_or_exact_head_unverified", check)
    return RuntimeGateDecision(app_id, True, "runtime_paths_and_exact_head_verified", check)


def decision_payload(decision: RuntimeGateDecision) -> dict[str, Any]:
    payload = asdict(decision)
    payload["check"]["workspace"] = str(decision.check.workspace)
    payload["check"]["command_path"] = str(decision.check.command_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed exact-head runtime activation gate")
    parser.add_argument("app_id")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        registry = load_registry(args.registry)
        app = next((item for item in registry["applications"] if item["app_id"] == args.app_id), None)
        if app is None:
            raise RuntimeGateError("application not found in registry")
        decision = assess_runtime_gate(app, repository_root=args.repository_root)
    except (OSError, json.JSONDecodeError, RuntimeGateError) as exc:
        parser.error(str(exc))
    print(json.dumps(decision_payload(decision), indent=2, ensure_ascii=False))
    return 0 if decision.eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
