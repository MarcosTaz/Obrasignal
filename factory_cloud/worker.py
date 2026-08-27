from __future__ import annotations

import argparse
import json
import signal
import threading
import time
from pathlib import Path
from typing import Any, Callable

from factory_cloud.control_plane import ACTIVATION_CODE, load_registry
from factory_cloud.orchestrator import DEFAULT_STATE_PATH, PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore


class WorkerHost:
    """Long-lived host loop for the persistent orchestrator.

    This is a real foreground worker process. It can survive ChatGPT turn boundaries
    only when an external process manager keeps/restarts this process. It does not
    itself provision hosting, daemonize, deploy, or acquire production authority.
    """

    def __init__(
        self,
        orchestrator: PersistentFactoryOrchestrator,
        poll_seconds: float = 5.0,
        max_dispatches_per_cycle: int = 100,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if poll_seconds < 0:
            raise ValueError("poll_seconds must be >= 0")
        self.orchestrator = orchestrator
        self.poll_seconds = poll_seconds
        self.max_dispatches_per_cycle = max(1, max_dispatches_per_cycle)
        self.sleeper = sleeper
        self.stop_event = threading.Event()
        self.last_cycle: dict[str, Any] | None = None

    def stop(self) -> None:
        self.stop_event.set()

    def run_once(self) -> dict[str, Any]:
        self.last_cycle = self.orchestrator.run_cycle(self.max_dispatches_per_cycle)
        return self.last_cycle

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
        return self.last_cycle


def _install_signal_handlers(host: WorkerHost) -> None:
    def request_stop(signum, frame):  # pragma: no cover - OS integration
        host.stop()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


def main() -> int:
    parser = argparse.ArgumentParser(description="Long-lived Factory Cloud worker host")
    parser.add_argument("code", help="activation code; must be Ω")
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--max-dispatches", type=int, default=100)
    parser.add_argument("--max-cycles", type=int, default=None, help="test/operator bound; omit for continuous foreground execution")
    args = parser.parse_args()
    if args.code != ACTIVATION_CODE:
        parser.error("Factory Cloud activation requires Ω")
    registry = load_registry(args.registry) if args.registry else load_registry()
    orchestrator = PersistentFactoryOrchestrator(registry, StateStore(args.state))
    host = WorkerHost(
        orchestrator,
        poll_seconds=args.poll_seconds,
        max_dispatches_per_cycle=args.max_dispatches,
    )
    _install_signal_handlers(host)
    result = host.run_forever(args.max_cycles)
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
