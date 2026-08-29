from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factory_cloud.process_adapter import ProcessAdapterConfig


class RuntimeProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeProvisioningCheck:
    app_id: str
    workspace: Path
    command_path: Path
    workspace_exists: bool
    command_exists: bool
    ready: bool


def inspect_runtime(config_path: str | Path, *, expected_app_id: str) -> RuntimeProvisioningCheck:
    config = ProcessAdapterConfig.load(Path(config_path), expected_app_id=expected_app_id)
    workspace = Path(config.workspace)
    if not workspace.is_absolute():
        raise RuntimeProvisioningError("runtime workspace must be absolute")
    if not config.command:
        raise RuntimeProvisioningError("runtime command is required")
    command_path = Path(config.command[-1])
    if not command_path.is_absolute():
        raise RuntimeProvisioningError("runtime agent command path must be absolute")
    workspace_exists = workspace.is_dir()
    command_exists = command_path.is_file()
    return RuntimeProvisioningCheck(
        app_id=expected_app_id,
        workspace=workspace,
        command_path=command_path,
        workspace_exists=workspace_exists,
        command_exists=command_exists,
        ready=workspace_exists and command_exists,
    )


def require_runtime(config_path: str | Path, *, expected_app_id: str) -> RuntimeProvisioningCheck:
    check = inspect_runtime(config_path, expected_app_id=expected_app_id)
    if not check.ready:
        missing: list[str] = []
        if not check.workspace_exists:
            missing.append(f"workspace:{check.workspace}")
        if not check.command_exists:
            missing.append(f"command:{check.command_path}")
        raise RuntimeProvisioningError("runtime not provisioned: " + ", ".join(missing))
    return check
