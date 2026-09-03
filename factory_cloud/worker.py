from __future__ import annotations

import argparse
import json
import signal
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from factory_cloud.adapters import AdapterRegistry
from factory_cloud.control_plane import ACTIVATION_CODE, load_registry
from factory_cloud.orchestrator import DEFAULT_STATE_PATH, PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore
from factory_cloud.verification import VerifiedDispatchAdapter
from factory_cloud.work_queue import QueuedAppAdapter, open_app_queue

LEASE_NAME = "factory_cloud_dispatch"


class WorkerHost:
    """Long-lived foreground host with durable single-dispatch authority.

    Crash recovery is deferred until this host owns the dispatch lease. That prevents
    a standby process from misclassifying a live worker's EXECUTING task as crashed.
    """

    def __init__(self, orchestrator: PersistentFactoryOrchestrator, poll_seconds: float = 5.0, max_dispatches_per_cycle: int = 100, sleeper: Callable[[float], None] = time.sleep, owner_id: str | None = None, lease_ttl_seconds: float | None = None):
        if poll_seconds < 0:
            raise ValueError("poll_seconds must be >= 0")
        self.orchestrator = orchestrator
        self.poll_seconds = poll_seconds
        self.max_dispatches_per_cycle = max(1, max_dispatches_per_cycle)
        self.sleeper = sleeper
        self.owner_id = owner_id or uuid.uuid4().hex
        self.lease_ttl_seconds = lease_ttl_seconds or max(15.0, poll_seconds * 4.0)
        self.stop_event = threading.Event()
        self.last_cycle: dict[str, Any] | None = None
        self._recovery_done = False

    @property
    def store(self) -> StateStore:
        return self.orchestrator.store

    def stop(self) -> None:
        self.stop_event.set()
        self.store.release_lease(LEASE_NAME, self.owner_id)

    def _heartbeat(self, stop: threading.Event) -> None:
        interval = max(0.1, self.lease_ttl_seconds / 3.0)
        while not stop.wait(interval):
            if not self.store.acquire_or_renew_lease(LEASE_NAME, self.owner_id, self.lease_ttl_seconds):
                self.stop_event.set()
                return

    def _standby(self) -> dict[str, Any]:
        return {"activation_code": ACTIVATION_CODE, "global_state": "STANDBY", "dispatches": [], "blockers": {"factory_cloud": ["dispatch_lease_held_by_another_worker"]}, "apps": self.store.list_apps()}

    def run_once(self) -> dict[str, Any]:
        if not self.store.acquire_or_renew_lease(LEASE_NAME, self.owner_id, self.lease_ttl_seconds):
            self.last_cycle = self._standby()
            return self.last_cycle
        if not self._recovery_done:
            self.orchestrator.recover_interrupted_executions()
            self._recovery_done = True
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(target=self._heartbeat, args=(heartbeat_stop,), daemon=True)
        heartbeat.start()
        try:
            self.last_cycle = self.orchestrator.run_cycle(self.max_dispatches_per_cycle)
            return self.last_cycle
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=max(1.0, self.lease_ttl_seconds / 3.0 + 0.5))

    def run_forever(self, max_cycles: int | None = None) -> dict[str, Any] | None:
        cycles = 0
        try:
            while not self.stop_event.is_set():
                self.run_once()
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    break
                if self.stop_event.is_set():
                    break
                self.sleeper(self.poll_seconds)
            return self.last_cycle
        finally:
            self.store.release_lease(LEASE_NAME, self.owner_id)


def _install_signal_handlers(host: WorkerHost) -> None:
    def request_stop(signum, frame):  # pragma: no cover
        host.stop()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


def _runtime_adapters(registry: dict[str, Any], queue_dir: Path) -> AdapterRegistry:
    overrides = {}
    for app in registry.get("applications", []):
        activation = app.get("activation") or {}
        canonical = app.get("source_truth") or {}
        if activation.get("enabled") is not True or activation.get("mode") != "repository_safe_execution":
            continue
        app_id = app["app_id"]
        delegate = QueuedAppAdapter(open_app_queue(queue_dir, app_id))
        execution = app.get("execution_source") or {}
        repository = str(execution.get("repository") or canonical.get("repository") or "")
        branch = str(execution.get("branch") or canonical.get("canonical_branch") or "")
        expected_head = execution.get("head") or canonical.get("canonical_head")
        provider = execution.get("provider") or canonical.get("provider")
        if provider == "github":
            delegate = VerifiedDispatchAdapter(delegate, repository=repository, branch=branch, expected_head=expected_head)
        overrides[app_id] = delegate
    return AdapterRegistry(overrides)


def main() -> int:
    parser = argparse.ArgumentParser(description="Long-lived Factory Cloud worker host")
    parser.add_argument("code", help="activation code; must be D")
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--queue-dir", type=Path, default=None, help="directory containing one physically isolated queue per app")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--max-dispatches", type=int, default=100)
    parser.add_argument("--lease-ttl-seconds", type=float, default=None)
    parser.add_argument("--max-cycles", type=int, default=None, help="test/operator bound; omit for continuous foreground execution")
    args = parser.parse_args()
    if args.code != ACTIVATION_CODE:
        parser.error("Factory Cloud activation requires D")
    registry = load_registry(args.registry) if args.registry else load_registry()
    store = StateStore(args.state)
    queue_dir = args.queue_dir or (args.state.parent / "queues")
    orchestrator = PersistentFactoryOrchestrator(registry, store, adapters=_runtime_adapters(registry, queue_dir), recover_interrupted=False)
    host = WorkerHost(orchestrator, poll_seconds=args.poll_seconds, max_dispatches_per_cycle=args.max_dispatches, lease_ttl_seconds=args.lease_ttl_seconds)
    _install_signal_handlers(host)
    result = host.run_forever(args.max_cycles)
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
