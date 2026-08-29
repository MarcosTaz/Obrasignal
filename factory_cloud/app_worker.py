from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from factory_cloud.adapters import AdapterRegistry, ExecutionRequest, ExecutionResult
from factory_cloud.control_plane import ACTIVATION_CODE
from factory_cloud.process_adapter import ProcessAdapterConfig, ProcessAdapterConfigError, ProcessAgentAdapter
from factory_cloud.work_queue import DurableWorkQueue, QueueStore


class AppWorkerHost:
    """Persistent worker restricted to exactly one app_id.

    App credentials/tooling belong to the injected adapter/environment, never to
    Factory Cloud metadata. Runtime queues are additionally expected to be
    physically scoped to this app_id.
    """

    def __init__(self, app_id: str, queue: DurableWorkQueue, adapters: AdapterRegistry | None = None, worker_id: str | None = None, poll_seconds: float = 5.0, job_lease_seconds: float = 60.0, sleeper: Callable[[float], None] = time.sleep):
        if not app_id:
            raise ValueError("app_id is required")
        if poll_seconds < 0 or job_lease_seconds <= 0:
            raise ValueError("valid poll and job lease are required")
        if queue.app_id_scope is not None and queue.app_id_scope != app_id:
            raise ValueError("worker queue scope must match app_id")
        self.app_id = app_id
        self.queue = queue
        self.adapters = adapters or AdapterRegistry()
        self.worker_id = worker_id or f"{app_id}-{uuid.uuid4().hex}"
        self.poll_seconds = poll_seconds
        self.job_lease_seconds = job_lease_seconds
        self.sleeper = sleeper
        self.stop_event = threading.Event()
        self.last_result: dict[str, Any] | None = None

    def stop(self) -> None:
        self.stop_event.set()

    def _heartbeat(self, job_id: str, stop: threading.Event) -> None:
        interval = max(0.1, self.job_lease_seconds / 3.0)
        while not stop.wait(interval):
            if not self.queue.renew_claim(job_id, self.worker_id, self.job_lease_seconds):
                self.stop_event.set()
                return

    def run_once(self) -> dict[str, Any]:
        job = self.queue.claim(self.app_id, self.worker_id, self.job_lease_seconds)
        if job is None:
            self.last_result = {"app_id": self.app_id, "state": "IDLE", "job_id": None}
            return self.last_result
        request = ExecutionRequest(**job["request"])
        if request.app_id != self.app_id:
            result = ExecutionResult(status="ERROR", evidence={"job_app_id": request.app_id, "worker_app_id": self.app_id}, blockers=("cross_app_worker_job_rejected",), resume_at=request.task, error={"type": "CROSS_APP_JOB"})
            self.queue.finish(job["job_id"], self.worker_id, result)
            self.last_result = {"app_id": self.app_id, "state": "ERROR", "job_id": job["job_id"], "result": asdict(result)}
            return self.last_result
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(target=self._heartbeat, args=(job["job_id"], heartbeat_stop), daemon=True)
        heartbeat.start()
        try:
            try:
                adapter = self.adapters.for_app(self.app_id, request.mode)
                result = adapter.execute(request)
            except Exception as exc:
                result = ExecutionResult(status="ERROR", evidence={"exception_type": type(exc).__name__}, blockers=("app_worker_adapter_error",), resume_at=request.task, error={"type": type(exc).__name__})
            self.queue.finish(job["job_id"], self.worker_id, result)
            self.last_result = {"app_id": self.app_id, "state": result.status, "job_id": job["job_id"], "result": asdict(result)}
            return self.last_result
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=max(1.0, self.job_lease_seconds / 3.0 + 0.5))

    def run_forever(self, max_cycles: int | None = None) -> dict[str, Any] | None:
        cycles = 0
        while not self.stop_event.is_set():
            self.run_once()
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            if self.stop_event.is_set():
                break
            self.sleeper(self.poll_seconds)
        return self.last_result


def _runtime_adapters(app_id: str, adapter_config: Path | None) -> AdapterRegistry:
    if adapter_config is None:
        return AdapterRegistry()
    config = ProcessAdapterConfig.load(adapter_config, expected_app_id=app_id)
    return AdapterRegistry({app_id: ProcessAgentAdapter(config)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated Factory Cloud application worker")
    parser.add_argument("code", help="activation code; must be D")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--queue", type=Path, required=True, help="physically isolated queue SQLite for this app")
    parser.add_argument("--adapter-config", type=Path, default=None, help="external app-owned process adapter JSON; must not contain secrets")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--job-lease-seconds", type=float, default=60.0)
    parser.add_argument("--max-cycles", type=int, default=None)
    args = parser.parse_args()
    if args.code != ACTIVATION_CODE:
        parser.error("Factory Cloud activation requires D")
    try:
        adapters = _runtime_adapters(args.app_id, args.adapter_config)
    except ProcessAdapterConfigError as exc:
        parser.error(str(exc))
    queue = DurableWorkQueue(QueueStore(args.queue), app_id_scope=args.app_id)
    host = AppWorkerHost(args.app_id, queue, adapters=adapters, poll_seconds=args.poll_seconds, job_lease_seconds=args.job_lease_seconds)
    result = host.run_forever(args.max_cycles)
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
