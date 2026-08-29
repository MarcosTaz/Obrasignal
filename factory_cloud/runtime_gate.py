from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
