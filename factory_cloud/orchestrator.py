from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from factory_cloud.adapters import AdapterRegistry, ExecutionRequest, ExecutionResult
from factory_cloud.control_plane import ACTIVATION_CODE, RegistryError, load_registry
from factory_cloud.portfolio_priority import PortfolioPriorityError, priority_for_app
from factory_cloud.state_store import StateStore, StateStoreError, utc_now

DEFAULT_STATE_PATH = Path(__file__).with_name("factory_cloud_state.sqlite3")
TERMINAL_SAFE_STATUSES = {"DONE", "WAIT", "BLOCKED", "ERROR"}
PENDING_WORKER_BLOCKER = "app_worker_execution_pending"
WAIT_RETRY_SECONDS = 60
BLOCKED_RETRY_SECONDS = 300
ERROR_RETRY_BASE_SECONDS = 30
MAX_RETRY_SECONDS = 900
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class DispatchDecision:
    app_id: str
    mode: str
    task: str
    source: str | None
    canonical_head: str | None
    resume_at: str
    execution_branch: str | None = None
    execution_head: str | None = None
    required_capabilities: tuple[str, ...] = ()


class OrchestratorError(RuntimeError):
    pass


def _future_retry_at(delay_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()


def _retry_gate_open(retry: dict[str, Any], task: str) -> bool:
    if retry.get("task") != task:
        return True
    raw = retry.get("next_attempt_at")
    if not raw:
        return True
    try:
        when = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return False
    if when.tzinfo is None or when.utcoffset() is None:
        return False
    return when.astimezone(timezone.utc) <= datetime.now(timezone.utc)


class PersistentFactoryOrchestrator:
    """Process-restart-safe Factory Cloud scheduler.

    Canonical source truth remains persisted separately from the mutable development
    execution source. A successful repository-safe task may advance only the latter.
    Portfolio priority signals affect scheduling only; they never grant execution
    capability, repository authority, production authority or cross-app data access.
    """

    def __init__(
        self,
        registry: dict[str, Any],
        store: StateStore,
        adapters: AdapterRegistry | None = None,
        recover_interrupted: bool = False,
    ):
        self.registry = registry
        self.store = store
        self.adapters = adapters or AdapterRegistry()
        self._apps = {app["app_id"]: app for app in registry.get("applications", [])}
        self.recover_registry()
        if recover_interrupted:
            self.recover_interrupted_executions()

    def recover_registry(self) -> None:
        for app in self.registry.get("applications", []):
            activation = app.get("activation") or {}
            if activation.get("enabled") is True:
                self.store.upsert_from_registry(app)

    def recover_interrupted_executions(self) -> None:
        """Close interrupted history and restore the exact task as RESUME_AT."""
        for app in self.store.list_apps():
            current = app.get("current_execution")
            if app.get("state") != "EXECUTING" or not current:
                continue
            task = str(current.get("task") or app.get("resume_at") or app.get("active") or "")
            execution_id = str(current.get("execution_id") or "").strip()
            retry = dict(app.get("retry_state") or {})
            interrupted_at = utc_now()
            retry["interrupted_count"] = int(retry.get("interrupted_count", 0)) + 1
            retry["last_interrupted_at"] = interrupted_at
            interruption = {"type": "PROCESS_INTERRUPTED", "task": task, "execution_id": execution_id or None}
            if execution_id:
                try:
                    self.store.finish_execution(
                        app["app_id"], execution_id, "INTERRUPTED",
                        {"recovered_at": interrupted_at, "resume_at": task}, interruption,
                    )
                except StateStoreError:
                    interruption["history_error"] = "interrupted_history_not_closable"
            self.store.checkpoint(
                app["app_id"], state="READY", active=task, resume_at=task,
                current_execution_json=None, retry_state_json=retry, error_state_json=interruption,
            )

    def _app_config(self, app_id: str) -> dict[str, Any]:
        try:
            return self._apps[app_id]
        except KeyError as exc:
            raise OrchestratorError(f"app missing from registry: {app_id}") from exc

    def _decision_for(self, state: dict[str, Any]) -> DispatchDecision | None:
        app = self._app_config(state["app_id"])
        activation = app.get("activation") or {}
        mode = activation.get("mode")
        if activation.get("enabled") is not True:
            return None
        active = str(state.get("active") or "").strip()
        next_items = list(state.get("next") or [])
        task = active or (str(next_items[0]) if next_items else "")
        if not task:
            return None
        if not _retry_gate_open(dict(state.get("retry_state") or {}), task):
            return None

        source_truth = app.get("source_truth") or {}
        canonical_source = (
            source_truth.get("repository")
            or source_truth.get("canonical_repository")
            or source_truth.get("project")
        )
        registry_execution = app.get("execution_source") or {}
        if mode == "repository_safe_execution":
            source = registry_execution.get("repository") or canonical_source
            execution_branch = (
                str(state.get("execution_branch") or "").strip()
                or str(registry_execution.get("branch") or "").strip()
                or str(source_truth.get("canonical_branch") or "").strip()
                or None
            )
            execution_head = (
                str(state.get("execution_head") or "").strip()
                or str(registry_execution.get("head") or "").strip()
                or str(state.get("canonical_head") or "").strip()
                or None
            )
        else:
            source = canonical_source
            execution_branch = None
            execution_head = None

        contracts = app.get("task_capabilities") or {}
        required_capabilities = tuple(str(value) for value in contracts.get(task, []))

        return DispatchDecision(
            app_id=state["app_id"], mode=mode, task=task, source=source,
            canonical_head=state.get("canonical_head"),
            resume_at=str(state.get("resume_at") or task),
            execution_branch=execution_branch, execution_head=execution_head,
            required_capabilities=required_capabilities,
        )

    def _priority_score(self, app_id: str) -> int:
        try:
            return priority_for_app(self._app_config(app_id)).score
        except PortfolioPriorityError as exc:
            raise OrchestratorError(f"invalid portfolio priority for {app_id}: {exc}") from exc

    def choose_next(self, attempted: set[str] | None = None) -> DispatchDecision | None:
        attempted = attempted or set()
        states = sorted(
            self.store.list_apps(),
            key=lambda state: (-self._priority_score(state["app_id"]), state["app_id"]),
        )
        for state in states:
            if state["app_id"] in attempted:
                continue
            decision = self._decision_for(state)
            if decision is not None:
                return decision
        return None

    def _validated_result(self, decision: DispatchDecision, result: ExecutionResult) -> ExecutionResult:
        if result.status not in TERMINAL_SAFE_STATUSES:
            return ExecutionResult(
                status="ERROR", evidence={"invalid_adapter_status": result.status}, next_active=decision.task,
                blockers=("invalid_adapter_status",), resume_at=decision.task,
                error={"type": "INVALID_ADAPTER_STATUS", "status": result.status},
            )
        has_branch = bool(result.execution_branch)
        has_head = bool(result.execution_head)
        if has_branch != has_head:
            return ExecutionResult(
                status="ERROR", evidence={"task_state": "INVALID_EXECUTION_SOURCE_RESULT"},
                next_active=decision.task, blockers=("invalid_execution_source_result",), resume_at=decision.task,
                error={"type": "INVALID_EXECUTION_SOURCE_RESULT"},
            )
        if has_head and (result.status != "DONE" or not _SHA_RE.fullmatch(str(result.execution_head))):
            return ExecutionResult(
                status="ERROR", evidence={"task_state": "INVALID_EXECUTION_SOURCE_RESULT"},
                next_active=decision.task, blockers=("invalid_execution_source_result",), resume_at=decision.task,
                error={"type": "INVALID_EXECUTION_SOURCE_RESULT"},
            )
        if has_branch:
            canonical_branch = str((self._app_config(decision.app_id).get("source_truth") or {}).get("canonical_branch") or "").strip()
            if canonical_branch and result.execution_branch == canonical_branch:
                return ExecutionResult(
                    status="ERROR", evidence={"task_state": "CANONICAL_BRANCH_MUTATION_REJECTED"},
                    next_active=decision.task, blockers=("canonical_branch_mutation_rejected",), resume_at=decision.task,
                    error={"type": "CANONICAL_BRANCH_MUTATION_REJECTED"},
                )
        return result

    def _checkpoint_result(self, decision: DispatchDecision, result: ExecutionResult) -> None:
        state = self.store.get_app(decision.app_id)
        if state is None:
            raise OrchestratorError(f"state vanished for {decision.app_id}")
        current_next = list(state.get("next") or [])
        if result.next_items:
            next_items = list(result.next_items)
        else:
            next_items = current_next
            if result.status == "DONE" and next_items and next_items[0] == decision.task:
                next_items = next_items[1:]
        next_active = result.next_active
        if result.status == "DONE" and not next_active:
            next_active = str(next_items[0]) if next_items else ""
        if result.status in {"WAIT", "BLOCKED", "ERROR"} and not next_active:
            next_active = decision.task
        wait_items = list(result.wait_items) if result.wait_items else list(state.get("wait") or [])
        blockers = list(result.blockers)
        retry = dict(state.get("retry_state") or {})
        now = utc_now()

        if result.status == "ERROR":
            attempts = int(retry.get("attempts", 0)) + 1
            delay = min(ERROR_RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)), MAX_RETRY_SECONDS)
            retry.update({"attempts": attempts, "last_error_at": now, "next_attempt_at": _future_retry_at(delay), "retry_reason": "ERROR", "task": decision.task})
        elif result.status in {"WAIT", "BLOCKED"} and PENDING_WORKER_BLOCKER not in blockers:
            wait_attempts = int(retry.get("wait_attempts", 0)) + 1
            base = WAIT_RETRY_SECONDS if result.status == "WAIT" else BLOCKED_RETRY_SECONDS
            delay = min(base * (2 ** max(0, wait_attempts - 1)), MAX_RETRY_SECONDS)
            retry.update({"wait_attempts": wait_attempts, "last_wait_at": now, "next_attempt_at": _future_retry_at(delay), "retry_reason": result.status, "task": decision.task})
        elif result.status == "DONE":
            retry = {}

        resume_at = (next_active or decision.task) if result.status == "DONE" else (result.resume_at or next_active or decision.task)
        checkpoint: dict[str, Any] = {
            "state": "READY" if result.status == "DONE" else result.status,
            "active": next_active,
            "next_json": next_items,
            "wait_json": wait_items,
            "blockers_json": blockers,
            "last_verified": result.last_verified or state.get("last_verified"),
            "last_green": result.last_green or result.execution_head or state.get("last_green"),
            "resume_at": resume_at,
            "current_execution_json": None,
            "error_state_json": result.error,
            "retry_state_json": retry,
        }
        if result.status == "DONE" and result.execution_head and result.execution_branch:
            checkpoint["execution_branch"] = result.execution_branch
            checkpoint["execution_head"] = result.execution_head
        self.store.checkpoint(decision.app_id, **checkpoint)

    def execute_one(self, decision: DispatchDecision) -> ExecutionResult:
        execution_id = uuid.uuid4().hex
        payload = {
            "execution_id": execution_id, "app_id": decision.app_id, "mode": decision.mode,
            "task": decision.task, "source": decision.source, "canonical_head": decision.canonical_head,
            "execution_branch": decision.execution_branch, "execution_head": decision.execution_head,
            "required_capabilities": list(decision.required_capabilities), "resume_at": decision.resume_at,
        }
        self.store.start_execution(decision.app_id, execution_id, decision.task, payload)
        adapter = self.adapters.for_app(decision.app_id, decision.mode)
        try:
            result = adapter.execute(
                ExecutionRequest(
                    app_id=decision.app_id, mode=decision.mode, task=decision.task,
                    source=decision.source, canonical_head=decision.canonical_head, resume_at=decision.resume_at,
                    execution_branch=decision.execution_branch, execution_head=decision.execution_head,
                    required_capabilities=decision.required_capabilities,
                )
            )
        except Exception as exc:
            result = ExecutionResult(
                status="ERROR", evidence={"exception_type": type(exc).__name__},
                next_active=decision.task, blockers=("adapter_execution_error",), resume_at=decision.task,
                error={"type": type(exc).__name__},
            )
        result = self._validated_result(decision, result)
        self.store.finish_execution(decision.app_id, execution_id, result.status, result.evidence, result.error)
        self._checkpoint_result(decision, result)
        return result

    def run_cycle(self, max_dispatches: int = 100) -> dict[str, Any]:
        attempted: set[str] = set()
        dispatches: list[dict[str, Any]] = []
        while len(dispatches) < max_dispatches:
            decision = self.choose_next(attempted)
            if decision is None:
                break
            result = self.execute_one(decision)
            dispatches.append({
                "app_id": decision.app_id,
                "task": decision.task,
                "status": result.status,
                "evidence": result.evidence,
                "portfolio_priority_score": self._priority_score(decision.app_id),
            })
            if result.status == "DONE":
                state = self.store.get_app(decision.app_id)
                if state and self._decision_for(state) is not None:
                    continue
            attempted.add(decision.app_id)
        states = self.store.list_apps()
        eligible = [self._decision_for(state) for state in states]
        global_wait = not any(item is not None and item.app_id not in attempted for item in eligible)
        return {
            "activation_code": ACTIVATION_CODE, "dispatches": dispatches,
            "global_state": "WAIT" if global_wait else "READY",
            "blockers": {state["app_id"]: state.get("blockers") or [] for state in states if state.get("blockers")},
            "apps": states,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistent Factory Cloud orchestrator")
    parser.add_argument("code", help="activation code; must be D")
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--max-dispatches", type=int, default=100)
    args = parser.parse_args()
    if args.code != ACTIVATION_CODE:
        parser.error("Factory Cloud activation requires D")
    try:
        registry = load_registry(args.registry) if args.registry else load_registry()
        orchestrator = PersistentFactoryOrchestrator(registry, StateStore(args.state), recover_interrupted=True)
        result = orchestrator.run_cycle(max_dispatches=max(1, args.max_dispatches))
    except (OSError, json.JSONDecodeError, RegistryError, OrchestratorError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
