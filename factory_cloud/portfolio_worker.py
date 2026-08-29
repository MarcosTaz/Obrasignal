from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class PortfolioWorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PortfolioExecutionRequest:
    factory_id: str
    route: str
    signal: str
    mission: str
    baton: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "factory_id": self.factory_id,
                "route": self.route,
                "signal": self.signal,
                "mission": self.mission,
                "baton": self.baton,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


def configured_executor(environ: dict[str, str] | None = None) -> Path | None:
    env = os.environ if environ is None else environ
    raw = str(env.get("FACTORY_CLOUD_PORTFOLIO_WORKER") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        raise PortfolioWorkerError("FACTORY_CLOUD_PORTFOLIO_WORKER must be an absolute executable path")
    return path


class PortfolioFactoryWorker:
    """One host-level execution boundary for every non-app Factory.

    Factory identity is delivered in the request body; founders do not configure a
    chat/conversation URL for every Factory. One isolated worker executable can
    multiplex Factory IDs while preserving per-Factory BATON state in the caller.
    """

    def __init__(
        self,
        *,
        environ: dict[str, str] | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: int = 1800,
    ) -> None:
        self.environ = dict(os.environ if environ is None else environ)
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def execute(self, request: PortfolioExecutionRequest) -> dict[str, Any]:
        try:
            executable = configured_executor(self.environ)
        except PortfolioWorkerError as exc:
            return {
                "status": "BLOCKED",
                "factory_id": request.factory_id,
                "route": request.route,
                "blockers": ["portfolio_worker_configuration_invalid"],
                "error": {"type": "INVALID_WORKER_CONFIGURATION", "detail": str(exc)},
                "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
            }
        if executable is None:
            return {
                "status": "WAIT",
                "factory_id": request.factory_id,
                "route": request.route,
                "blockers": ["portfolio_factory_worker_not_provisioned"],
                "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
            }

        try:
            completed = self.runner(
                [str(executable)],
                input=request.to_json(),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                env=self.environ,
            )
        except (OSError, subprocess.SubprocessError):
            return {
                "status": "ERROR",
                "factory_id": request.factory_id,
                "route": request.route,
                "blockers": ["portfolio_factory_worker_execution_failed"],
                "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
                "error": {"type": "WORKER_EXECUTION_FAILED"},
            }

        if completed.returncode != 0:
            return {
                "status": "ERROR",
                "factory_id": request.factory_id,
                "route": request.route,
                "blockers": ["portfolio_factory_worker_nonzero_exit"],
                "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
                "error": {"type": "WORKER_NONZERO_EXIT", "code": completed.returncode},
            }

        try:
            payload = json.loads(completed.stdout or "")
        except json.JSONDecodeError:
            return {
                "status": "ERROR",
                "factory_id": request.factory_id,
                "route": request.route,
                "blockers": ["portfolio_factory_worker_invalid_result"],
                "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
                "error": {"type": "INVALID_WORKER_RESULT"},
            }
        if not isinstance(payload, dict):
            return {
                "status": "ERROR",
                "factory_id": request.factory_id,
                "route": request.route,
                "blockers": ["portfolio_factory_worker_invalid_result"],
                "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
                "error": {"type": "INVALID_WORKER_RESULT"},
            }
        payload.setdefault("factory_id", request.factory_id)
        payload.setdefault("route", request.route)
        return payload
