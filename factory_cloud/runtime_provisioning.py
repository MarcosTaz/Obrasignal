from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
    expected_head: str | None
    observed_head: str | None
    head_matches: bool
    ready: bool


def _read_git_head(workspace: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    head = (completed.stdout or "").strip()
    return head or None


def inspect_runtime(
    config_path: str | Path,
    *,
    expected_app_id: str,
    expected_head: str | None = None,
    head_reader: Callable[[Path], str | None] = _read_git_head,
) -> RuntimeProvisioningCheck:
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
    observed_head = head_reader(workspace) if workspace_exists else None
    head_matches = expected_head is None or observed_head == expected_head
    ready = workspace_exists and command_exists and head_matches
    return RuntimeProvisioningCheck(
        app_id=expected_app_id,
        workspace=workspace,
        command_path=command_path,
        workspace_exists=workspace_exists,
        command_exists=command_exists,
        expected_head=expected_head,
        observed_head=observed_head,
        head_matches=head_matches,
        ready=ready,
    )


def require_runtime(
    config_path: str | Path,
    *,
    expected_app_id: str,
    expected_head: str | None = None,
    head_reader: Callable[[Path], str | None] = _read_git_head,
) -> RuntimeProvisioningCheck:
    check = inspect_runtime(
        config_path,
        expected_app_id=expected_app_id,
        expected_head=expected_head,
        head_reader=head_reader,
    )
    if not check.ready:
        blockers: list[str] = []
        if not check.workspace_exists:
            blockers.append(f"workspace:{check.workspace}")
        if not check.command_exists:
            blockers.append(f"command:{check.command_path}")
        if check.workspace_exists and not check.head_matches:
            blockers.append(f"head:expected={check.expected_head},observed={check.observed_head}")
        raise RuntimeProvisioningError("runtime not provisioned: " + ", ".join(blockers))
    return check
