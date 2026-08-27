import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore
from factory_cloud.worker import WorkerHost


class WaitingAdapter:
    def __init__(self):
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return ExecutionResult(status="WAIT", blockers=("external_boundary",), resume_at=request.task)


class FactoryCloudWorkerHostTests(unittest.TestCase):
    def test_foreground_worker_repeats_cycles_without_resetting_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = WaitingAdapter()
            k3 = WaitingAdapter()
            store = StateStore(Path(tmp) / "state.sqlite3")
            orchestrator = PersistentFactoryOrchestrator(
                load_registry(),
                store,
                AdapterRegistry({"obrasignal": obra, "k3-fatality": k3}),
            )
            sleeps = []
            host = WorkerHost(orchestrator, poll_seconds=0.01, sleeper=sleeps.append)
            final = host.run_forever(max_cycles=2)

            self.assertEqual(final["global_state"], "WAIT")
            self.assertEqual(obra.calls, 2)
            self.assertEqual(k3.calls, 2)
            self.assertEqual(sleeps, [0.01])
            self.assertEqual(len(store.history("obrasignal")), 2)
            self.assertEqual(len(store.history("k3-fatality")), 2)

    def test_stop_prevents_another_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "state.sqlite3")
            orchestrator = PersistentFactoryOrchestrator(load_registry(), store)
            host = WorkerHost(orchestrator, poll_seconds=0, sleeper=lambda _: None)
            host.stop()
            self.assertIsNone(host.run_forever())
            self.assertEqual(store.history("obrasignal"), [])


if __name__ == "__main__":
    unittest.main()
