from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import requests


class PortfolioWorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PortfolioExecutionRequest:
    factory_id: str
    route: str
    signal: str
    mission: str
    baton: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        return {
            "factory_id": self.factory_id,
            "route": self.route,
            "signal": self.signal,
            "mission": self.mission,
            "baton": self.baton,
        }

    def to_json(self) -> str:
        return json.dumps(self.payload(), ensure_ascii=False, sort_keys=True)


def configured_executor(environ: dict[str, str] | None = None) -> Path | None:
    env = os.environ if environ is None else environ
    raw = str(env.get("FACTORY_CLOUD_PORTFOLIO_WORKER") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        raise PortfolioWorkerError("FACTORY_CLOUD_PORTFOLIO_WORKER must be an absolute executable path")
    return path


def configured_endpoint(environ: dict[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    raw = str(env.get("FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT") or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise PortfolioWorkerError("FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT must be an absolute HTTP(S) URL")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise PortfolioWorkerError("remote portfolio worker endpoint must use HTTPS")
    if parsed.username or parsed.password:
        raise PortfolioWorkerError("portfolio worker endpoint credentials must not be embedded in URL")
    return raw.rstrip("/")


def _base_result(request: PortfolioExecutionRequest) -> dict[str, Any]:
    return {
        "factory_id": request.factory_id,
        "route": request.route,
        "resume_at": request.baton.get("resume_at") or request.baton.get("active"),
    }


class PortfolioFactoryWorker:
    """One host-level execution boundary for every non-app Factory.

    Factory identity is delivered in the request body; founders do not configure a
    chat/conversation URL for every Factory. One isolated worker executable OR one
    shared HTTPS worker endpoint can multiplex Factory IDs while the Control Tower
    preserves independent per-Factory BATON state.
    """

    def __init__(
        self,
        *,
        environ: dict[str, str] | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        poster: Callable[..., Any] = requests.post,
        timeout_seconds: int = 1800,
    ) -> None:
        self.environ = dict(os.environ if environ is None else environ)
        self.runner = runner
        self.poster = poster
        self.timeout_seconds = timeout_seconds

    def _configuration(self) -> tuple[Path | None, str | None] | dict[str, Any]:
        try:
            executable = configured_executor(self.environ)
            endpoint = configured_endpoint(self.environ)
        except PortfolioWorkerError as exc:
            return {
                "status": "BLOCKED",
                "blockers": ["portfolio_worker_configuration_invalid"],
                "error": {"type": "INVALID_WORKER_CONFIGURATION", "detail": str(exc)},
            }
        if executable is not None and endpoint is not None:
            return {
                "status": "BLOCKED",
                "blockers": ["portfolio_worker_configuration_ambiguous"],
                "error": {"type": "AMBIGUOUS_WORKER_CONFIGURATION"},
            }
        return executable, endpoint

    def execute(self, request: PortfolioExecutionRequest) -> dict[str, Any]:
        config = self._configuration()
        if isinstance(config, dict):
            return {**_base_result(request), **config}
        executable, endpoint = config
        if endpoint is not None:
            return self._execute_endpoint(request, endpoint)
        if executable is not None:
            return self._execute_executable(request, executable)
        return {
            **_base_result(request),
            "status": "WAIT",
            "blockers": ["portfolio_factory_worker_not_provisioned"],
        }

    def _execute_endpoint(self, request: PortfolioExecutionRequest, endpoint: str) -> dict[str, Any]:
        headers = {"content-type": "application/json", "accept": "application/json"}
        token = str(self.environ.get("FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN") or "").strip()
        if token:
            headers["authorization"] = f"Bearer {token}"
        try:
            response = self.poster(
                endpoint,
                json=request.payload(),
                headers=headers,
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
        except requests.RequestException:
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_endpoint_failed"],
                "error": {"type": "WORKER_ENDPOINT_FAILED"},
            }
        except Exception:
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_endpoint_failed"],
                "error": {"type": "WORKER_ENDPOINT_FAILED"},
            }
        if not 200 <= int(response.status_code) < 300:
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_endpoint_non_success"],
                "error": {"type": "WORKER_ENDPOINT_NON_SUCCESS", "code": int(response.status_code)},
            }
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_invalid_result"],
                "error": {"type": "INVALID_WORKER_RESULT"},
            }
        return self._validated_payload(request, payload)

    def _execute_executable(self, request: PortfolioExecutionRequest, executable: Path) -> dict[str, Any]:
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
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_execution_failed"],
                "error": {"type": "WORKER_EXECUTION_FAILED"},
            }

        if completed.returncode != 0:
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_nonzero_exit"],
                "error": {"type": "WORKER_NONZERO_EXIT", "code": completed.returncode},
            }

        try:
            payload = json.loads(completed.stdout or "")
        except json.JSONDecodeError:
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_invalid_result"],
                "error": {"type": "INVALID_WORKER_RESULT"},
            }
        return self._validated_payload(request, payload)

    def _validated_payload(self, request: PortfolioExecutionRequest, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                **_base_result(request),
                "status": "ERROR",
                "blockers": ["portfolio_factory_worker_invalid_result"],
                "error": {"type": "INVALID_WORKER_RESULT"},
            }
        payload.setdefault("factory_id", request.factory_id)
        payload.setdefault("route", request.route)
        return payload
