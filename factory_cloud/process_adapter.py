from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from factory_cloud.adapters import ExecutionRequest, ExecutionResult
from factory_cloud.capabilities import Capability, CapabilityContractError, parse_capabilities, require_capabilities

SAFE_STATUSES = {"DONE", "WAIT", "BLOCKED", "ERROR"}
MAX_METADATA_TEXT = 512
MAX_METADATA_ITEMS = 50
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ProcessAdapterConfigError(ValueError):
    pass


def _bounded_text(value: Any, *, field: str, allow_empty: bool = True) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProcessAdapterConfigError(f"{field} must be a string")
    value = value.strip()
    if not allow_empty and not value:
        raise ProcessAdapterConfigError(f"{field} must not be empty")
    if len(value) > MAX_METADATA_TEXT:
        raise ProcessAdapterConfigError(f"{field} exceeds metadata limit")
    return value


def _bounded_text_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > MAX_METADATA_ITEMS:
        raise ProcessAdapterConfigError(f"{field} must be a bounded list")
    return tuple(_bounded_text(item, field=field, allow_empty=False) for item in value)


def _safe_evidence(value: Any) -> dict[str, Any]:
    """Persist only a narrow metadata contract; never raw process output."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProcessAdapterConfigError("evidence must be an object")
    allowed: dict[str, Any] = {}
    for key in ("commit_sha", "verified_head", "test_state", "task_state", "work_branch", "pr_number"):
        if key in value:
            allowed[key] = _bounded_text(str(value[key]), field=f"evidence.{key}", allow_empty=False)
    if "evidence_codes" in value:
        allowed["evidence_codes"] = list(_bounded_text_tuple(value["evidence_codes"], field="evidence.evidence_codes"))
    return allowed


@dataclass(frozen=True)
class ProcessAdapterConfig:
    app_id: str
    mode: str
    workspace: Path
    command: tuple[str, ...]
    capabilities: frozenset[Capability]
    timeout_seconds: float = 1800.0

    @classmethod
    def load(cls, path: Path, *, expected_app_id: str) -> "ProcessAdapterConfig":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProcessAdapterConfigError("adapter config is unreadable or invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProcessAdapterConfigError("adapter config must be an object")
        app_id = _bounded_text(payload.get("app_id"), field="app_id", allow_empty=False)
        if app_id != expected_app_id:
            raise ProcessAdapterConfigError("adapter config app_id does not match worker app_id")
        mode = _bounded_text(payload.get("mode"), field="mode", allow_empty=False)
        if mode != "repository_safe_execution":
            raise ProcessAdapterConfigError("process adapters are allowed only for repository_safe_execution")
        workspace_text = _bounded_text(payload.get("workspace"), field="workspace", allow_empty=False)
        workspace = Path(workspace_text)
        if not workspace.is_absolute():
            raise ProcessAdapterConfigError("workspace must be an absolute path")
        command_value = payload.get("command")
        if not isinstance(command_value, list) or not command_value:
            raise ProcessAdapterConfigError("command must be a non-empty argv list")
        command = tuple(_bounded_text(item, field="command", allow_empty=False) for item in command_value)
        try:
            capabilities = parse_capabilities(payload.get("capabilities"), require_explicit=True)
        except CapabilityContractError as exc:
            raise ProcessAdapterConfigError(str(exc)) from exc
        timeout_value = payload.get("timeout_seconds", 1800.0)
        if not isinstance(timeout_value, (int, float)) or isinstance(timeout_value, bool):
            raise ProcessAdapterConfigError("timeout_seconds must be numeric")
        timeout_seconds = float(timeout_value)
        if timeout_seconds <= 0 or timeout_seconds > 21600:
            raise ProcessAdapterConfigError("timeout_seconds must be > 0 and <= 21600")
        return cls(app_id=app_id, mode=mode, workspace=workspace, command=command, capabilities=capabilities, timeout_seconds=timeout_seconds)


class ProcessAgentAdapter:
    """Run one isolated app-owned executable under a strict JSON metadata contract."""

    def __init__(self, config: ProcessAdapterConfig, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run):
        self.config = config
        self.runner = runner

    def _run(self, argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return self.runner(list(argv), **kwargs)

    def _observed_local_head(self) -> str | None:
        try:
            completed = self._run(("git", "rev-parse", "HEAD"), cwd=self.config.workspace, text=True, capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        head = (completed.stdout or "").strip()
        return head or None

    def _error(self, request: ExecutionRequest, blocker: str, error_type: str, **evidence: Any) -> ExecutionResult:
        return ExecutionResult(
            status="ERROR", evidence={"adapter": "process_agent", **evidence}, next_active=request.task,
            blockers=(blocker,), resume_at=request.task, error={"type": error_type},
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.app_id != self.config.app_id or request.mode != self.config.mode:
            return self._error(request, "app_worker_adapter_identity_mismatch", "ADAPTER_IDENTITY_MISMATCH")
        try:
            require_capabilities(self.config.capabilities, request.required_capabilities)
        except CapabilityContractError:
            return ExecutionResult(
                status="BLOCKED",
                evidence={
                    "adapter": "process_agent", "task_state": "AUTHORITY_REQUIRED",
                    "required_capabilities": list(request.required_capabilities),
                    "declared_capabilities": sorted(item.value for item in self.config.capabilities),
                },
                next_active=request.task, blockers=("adapter_capability_required",), resume_at=request.task,
            )
        if not self.config.workspace.is_dir():
            return ExecutionResult(status="WAIT", evidence={"adapter": "process_agent", "workspace_state": "UNAVAILABLE"}, next_active=request.task, blockers=("app_workspace_unavailable",), resume_at=request.task)
        expected_head = request.target_head
        if not expected_head:
            return ExecutionResult(status="WAIT", evidence={"adapter": "process_agent", "source_truth": "EXECUTION_HEAD_MISSING"}, next_active=request.task, blockers=("execution_source_truth_required_before_repository_execution",), resume_at=request.task)
        observed_head = self._observed_local_head()
        if observed_head is None:
            return ExecutionResult(status="WAIT", evidence={"adapter": "process_agent", "local_head_state": "UNVERIFIABLE"}, next_active=request.task, blockers=("local_workspace_head_unverifiable",), resume_at=request.task)
        if observed_head != expected_head:
            return ExecutionResult(
                status="WAIT",
                evidence={"adapter": "process_agent", "expected_head": expected_head, "observed_head": observed_head, "canonical_head": request.canonical_head, "execution_head": request.execution_head},
                next_active=request.task, blockers=("local_workspace_head_mismatch",), resume_at=request.task,
            )

        payload = json.dumps(
            {
                "app_id": request.app_id, "mode": request.mode, "task": request.task, "source": request.source,
                "canonical_head": request.canonical_head, "execution_branch": request.execution_branch,
                "execution_head": request.execution_head, "required_capabilities": list(request.required_capabilities),
                "resume_at": request.resume_at,
            },
            ensure_ascii=False,
        )
        try:
            completed = self._run(self.config.command, cwd=self.config.workspace, input=payload, text=True, capture_output=True, timeout=self.config.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return self._error(request, "app_agent_timeout", "APP_AGENT_TIMEOUT")
        except (OSError, subprocess.SubprocessError):
            return self._error(request, "app_agent_unavailable", "APP_AGENT_UNAVAILABLE")
        if completed.returncode != 0:
            return self._error(request, "app_agent_nonzero_exit", "APP_AGENT_NONZERO_EXIT", exit_code=int(completed.returncode))
        try:
            raw = json.loads((completed.stdout or "").strip())
            if not isinstance(raw, dict):
                raise ProcessAdapterConfigError("result must be an object")
            status = _bounded_text(raw.get("status"), field="status", allow_empty=False)
            if status not in SAFE_STATUSES:
                raise ProcessAdapterConfigError("invalid result status")
            result_execution_branch = _bounded_text(raw.get("execution_branch"), field="execution_branch") or None
            result_execution_head = _bounded_text(raw.get("execution_head"), field="execution_head") or None
            if bool(result_execution_branch) != bool(result_execution_head):
                raise ProcessAdapterConfigError("execution_branch and execution_head must be returned together")
            if result_execution_head and not SHA_RE.fullmatch(result_execution_head):
                raise ProcessAdapterConfigError("execution_head must be an exact lowercase git SHA")
            result = ExecutionResult(
                status=status,
                evidence={"adapter": "process_agent", "local_head": observed_head, **_safe_evidence(raw.get("evidence"))},
                next_active=_bounded_text(raw.get("next_active"), field="next_active"),
                next_items=_bounded_text_tuple(raw.get("next_items"), field="next_items"),
                wait_items=_bounded_text_tuple(raw.get("wait_items"), field="wait_items"),
                blockers=_bounded_text_tuple(raw.get("blockers"), field="blockers"),
                resume_at=_bounded_text(raw.get("resume_at"), field="resume_at"),
                last_verified=_bounded_text(raw.get("last_verified"), field="last_verified") or None,
                last_green=_bounded_text(raw.get("last_green"), field="last_green") or None,
                execution_branch=result_execution_branch, execution_head=result_execution_head,
                error={"type": _bounded_text((raw.get("error") or {}).get("type"), field="error.type", allow_empty=False)}
                if isinstance(raw.get("error"), dict) and raw.get("error", {}).get("type") else None,
            )
        except (json.JSONDecodeError, ProcessAdapterConfigError, TypeError):
            return self._error(request, "app_agent_invalid_result", "APP_AGENT_INVALID_RESULT")
        return result
