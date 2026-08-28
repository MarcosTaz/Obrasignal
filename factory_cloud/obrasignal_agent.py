from __future__ import annotations

"""Concrete, non-mutating ObraSignal execution adapter for Factory Cloud.

The agent accepts one Factory Cloud ExecutionRequest JSON object on stdin and emits
one metadata-only ExecutionResult JSON object on stdout. It deliberately supports
only a small verification allowlist. Task text is never interpolated into shell
commands and subprocess output is never copied into the result contract.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

# The process adapter deliberately launches this file by absolute path while using
# the application checkout as cwd. Make the Factory Cloud package importable from
# its own installation root without depending on cwd/PYTHONPATH or app-owned env.
if __package__ in {None, ""}:
    control_root = str(Path(__file__).resolve().parents[1])
    if control_root not in sys.path:
        sys.path.insert(0, control_root)

from factory_cloud.capabilities import Capability, CapabilityContractError, parse_capabilities, require_capabilities

APP_ID = "obrasignal"
MODE = "repository_safe_execution"
SOURCE = "MarcosTaz/Obrasignal"
TASK_COMPILE = "verify:execution:compile"
TASK_PYTHON = "verify:execution:python"
TASK_MOBILE = "verify:execution:mobile"
TASK_QUALITY = "verify:execution:quality"
ALLOWED_TASKS = frozenset({TASK_COMPILE, TASK_PYTHON, TASK_MOBILE, TASK_QUALITY})
AGENT_CAPABILITIES = frozenset({Capability.READ_REPOSITORY, Capability.RUN_TESTS, Capability.UPDATE_BATON})
TASK_REQUIRED_CAPABILITIES = {
    task: AGENT_CAPABILITIES
    for task in ALLOWED_TASKS
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
COMMAND_TIMEOUT_SECONDS = 1200
READ_ONLY_COMPILE_SCRIPT = (
    "import pathlib,sys\n"
    "for name in sys.argv[1:]:\n"
    " path=pathlib.Path(name)\n"
    " compile(path.read_text(encoding='utf-8'), str(path), 'exec')\n"
)


class ObraSignalAgentError(ValueError):
    pass


def _text(value: Any, field: str, *, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ObraSignalAgentError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ObraSignalAgentError(f"{field} is required")
    return value


def _request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ObraSignalAgentError("request must be an object")
    app_id = _text(payload.get("app_id"), "app_id")
    mode = _text(payload.get("mode"), "mode")
    task = _text(payload.get("task"), "task")
    source = _text(payload.get("source"), "source")
    canonical_head = _text(payload.get("canonical_head"), "canonical_head")
    execution_branch = _text(payload.get("execution_branch"), "execution_branch", required=False) or None
    execution_head = _text(payload.get("execution_head"), "execution_head", required=False) or None
    resume_at = _text(payload.get("resume_at"), "resume_at", required=False) or task
    raw_capabilities = payload.get("required_capabilities")
    if not isinstance(raw_capabilities, list):
        raise ObraSignalAgentError("required_capabilities must be an explicit list")
    try:
        required_capabilities = parse_capabilities(raw_capabilities, require_explicit=True)
    except CapabilityContractError as exc:
        raise ObraSignalAgentError(str(exc)) from exc
    if app_id != APP_ID:
        raise ObraSignalAgentError("wrong app_id")
    if mode != MODE:
        raise ObraSignalAgentError("wrong execution mode")
    if source != SOURCE:
        raise ObraSignalAgentError("wrong repository source")
    if not SHA_RE.fullmatch(canonical_head):
        raise ObraSignalAgentError("canonical_head must be a lowercase 40-character git SHA")
    if execution_head is not None and not SHA_RE.fullmatch(execution_head):
        raise ObraSignalAgentError("execution_head must be a lowercase 40-character git SHA")
    if execution_head is not None and execution_branch is None:
        raise ObraSignalAgentError("execution_branch is required with execution_head")
    return {
        "app_id": app_id,
        "mode": mode,
        "task": task,
        "source": source,
        "canonical_head": canonical_head,
        "execution_branch": execution_branch,
        "execution_head": execution_head,
        "required_capabilities": required_capabilities,
        "resume_at": resume_at,
    }


class ObraSignalVerificationAgent:
    def __init__(
        self,
        workspace: Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        environ: dict[str, str] | None = None,
    ) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        self.runner = runner
        self.environ = dict(os.environ if environ is None else environ)

    def _run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout: int = COMMAND_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self.runner(
            list(argv),
            cwd=cwd or self.workspace,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )

    def _head(self) -> str | None:
        try:
            completed = self._run(("git", "rev-parse", "HEAD"), timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        value = (completed.stdout or "").strip()
        return value if SHA_RE.fullmatch(value) else None

    @staticmethod
    def _wait(task: str, head: str | None, blocker: str, code: str) -> dict[str, Any]:
        return {
            "status": "WAIT",
            "evidence": {
                "verified_head": head or "UNVERIFIED",
                "test_state": "NOT_RUN",
                "task_state": code,
                "evidence_codes": [code],
            },
            "next_active": task,
            "blockers": [blocker],
            "resume_at": task,
        }

    @staticmethod
    def _error(task: str, head: str, error_type: str, code: str) -> dict[str, Any]:
        return {
            "status": "ERROR",
            "evidence": {
                "verified_head": head,
                "test_state": "FAILURE",
                "task_state": code,
                "evidence_codes": [code],
            },
            "next_active": task,
            "blockers": ["obrasignal_verification_failed"],
            "resume_at": task,
            "error": {"type": error_type},
            "last_verified": head,
        }

    def _python_context(self) -> tuple[str, list[str], list[str], dict[str, str]]:
        python = self.environ.get("FACTORY_CLOUD_OBRASIGNAL_PYTHON", sys.executable)
        root_modules = sorted(path.name for path in self.workspace.glob("*.py") if path.is_file())
        root_tests = sorted(path.name for path in self.workspace.glob("test_*.py") if path.is_file())
        env = dict(self.environ)
        prior = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(self.workspace) + (os.pathsep + prior if prior else "")
        return python, root_modules, root_tests, env

    def _run_compile(self) -> tuple[bool, str]:
        python, root_modules, _, env = self._python_context()
        if not root_modules:
            return False, "compile_targets_unavailable"
        try:
            completed = self._run(
                [python, "-c", READ_ONLY_COMPILE_SCRIPT, *root_modules],
                cwd=self.workspace,
                env=env,
            )
        except (OSError, subprocess.SubprocessError):
            return False, "compile_tool_unavailable"
        if completed.returncode != 0:
            return False, "compile_failed"
        return True, "compile_green"

    def _run_python(self) -> tuple[bool, str]:
        python, _, root_tests, env = self._python_context()
        compiled, compile_code = self._run_compile()
        if not compiled:
            if compile_code == "compile_tool_unavailable":
                return False, "python_tool_unavailable"
            return False, "python_verification_failed"
        try:
            completed = self._run(
                [python, "-m", "pytest", "-q", "--import-mode=importlib", "tests", *root_tests],
                cwd=self.workspace,
                env=env,
            )
        except (OSError, subprocess.SubprocessError):
            return False, "python_tool_unavailable"
        if completed.returncode != 0:
            return False, "python_verification_failed"
        return True, "python_green"

    def _run_mobile(self) -> tuple[bool | None, str]:
        mobile = self.workspace / "mobile"
        if not mobile.is_dir():
            return None, "mobile_workspace_unavailable"
        if not (mobile / "node_modules").is_dir():
            return None, "mobile_dependencies_unavailable"
        commands = (
            ("npx", "--no-install", "expo-doctor"),
            ("npm", "run", "smoke:detail"),
            ("npm", "run", "smoke:web"),
        )
        for argv in commands:
            try:
                completed = self._run(argv, cwd=mobile, env=dict(self.environ))
            except (OSError, subprocess.SubprocessError):
                return False, "mobile_tool_unavailable"
            if completed.returncode != 0:
                return False, "mobile_verification_failed"
        return True, "mobile_green"

    def execute(self, payload: Any) -> dict[str, Any]:
        try:
            request = _request(payload)
        except ObraSignalAgentError:
            return {
                "status": "ERROR",
                "evidence": {"test_state": "NOT_RUN", "task_state": "invalid_request", "evidence_codes": ["invalid_request"]},
                "blockers": ["obrasignal_agent_invalid_request"],
                "error": {"type": "INVALID_REQUEST"},
            }

        task = str(request["task"])
        expected = str(request.get("execution_head") or request["canonical_head"])
        if task not in ALLOWED_TASKS:
            return self._wait(task, None, "obrasignal_agent_task_not_allowlisted", "task_not_allowlisted")
        expected_caps = TASK_REQUIRED_CAPABILITIES[task]
        requested_caps = request["required_capabilities"]
        if requested_caps != expected_caps:
            return {
                "status": "BLOCKED",
                "evidence": {
                    "test_state": "NOT_RUN",
                    "task_state": "AUTHORITY_REQUIRED",
                    "evidence_codes": ["capability_contract_mismatch"],
                },
                "next_active": task,
                "blockers": ["obrasignal_agent_capability_contract_mismatch"],
                "resume_at": task,
            }
        try:
            require_capabilities(AGENT_CAPABILITIES, requested_caps)
        except CapabilityContractError:
            return {
                "status": "BLOCKED",
                "evidence": {
                    "test_state": "NOT_RUN",
                    "task_state": "AUTHORITY_REQUIRED",
                    "evidence_codes": ["agent_capability_missing"],
                },
                "next_active": task,
                "blockers": ["obrasignal_agent_capability_required"],
                "resume_at": task,
            }
        if not self.workspace.is_dir():
            return self._wait(task, None, "obrasignal_workspace_unavailable", "workspace_unavailable")
        observed = self._head()
        if observed is None:
            return self._wait(task, None, "local_workspace_head_unverifiable", "head_unverifiable")
        if observed != expected:
            return self._wait(task, observed, "local_workspace_head_mismatch", "head_mismatch")

        evidence_codes: list[str] = []
        if task == TASK_COMPILE:
            ok, code = self._run_compile()
            evidence_codes.append(code)
            if not ok:
                return self._error(task, observed, "COMPILE_VERIFICATION_FAILED", code)

        if task in {TASK_PYTHON, TASK_QUALITY}:
            ok, code = self._run_python()
            evidence_codes.append(code)
            if not ok:
                return self._error(task, observed, "PYTHON_VERIFICATION_FAILED", code)

        if task in {TASK_MOBILE, TASK_QUALITY}:
            ok, code = self._run_mobile()
            evidence_codes.append(code)
            if ok is None:
                result = self._wait(task, observed, "mobile_dependencies_required_on_app_workspace", code)
                result["evidence"]["evidence_codes"] = evidence_codes
                if "python_green" in evidence_codes:
                    result["evidence"]["test_state"] = "PARTIAL_SUCCESS"
                result["last_verified"] = observed
                return result
            if not ok:
                result = self._error(task, observed, "MOBILE_VERIFICATION_FAILED", code)
                result["evidence"]["evidence_codes"] = evidence_codes
                return result

        return {
            "status": "DONE",
            "evidence": {
                "commit_sha": observed,
                "verified_head": observed,
                "test_state": "SUCCESS",
                "task_state": "verification_complete",
                "evidence_codes": evidence_codes,
            },
            "blockers": [],
            "last_verified": observed,
            "last_green": observed,
        }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        payload = None
    result = ObraSignalVerificationAgent().execute(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
