import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore
from factory_cloud.worker import LEASE_NAME, WorkerHost


class WaitingAdapter:
    def __init__(self):
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return ExecutionResult(status="WAIT", blockers=("external_boundary",), resume_at=request.task)


class FactoryCloudWorkerHostTests(unittest.TestCase):
    def test_foreground_worker_repeats_cycles_without_retrying_unchanged_wait_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            obra = WaitingAdapter()
            k3 = WaitingAdapter()
            store = StateStore(Path(tmp) / "state.sqlite3")
            orchestrator = PersistentFactoryOrchestrator(
                load_registry(), store, AdapterRegistry({"obrasignal": obra, "k3-fatality": k3})
            )
            sleeps = []
            host = WorkerHost(orchestrator, poll_seconds=0.01, sleeper=sleeps.append, owner_id="worker-a")
            final = host.run_forever(max_cycles=2)
            self.assertEqual(final["global_state"], "WAIT")
            self.assertEqual(obra.calls, 1)
            self.assertEqual(k3.calls, 1)
            self.assertEqual(sleeps, [0.01])
            self.assertEqual(len(store.history("obrasignal")), 1)
            self.assertEqual(len(store.history("k3-fatality")), 1)
            self.assertIn("next_attempt_at", store.get_app("obrasignal")["retry_state"])
            self.assertIn("next_attempt_at", store.get_app("k3-fatality")["retry_state"])
            self.assertIsNone(store.lease(LEASE_NAME))

    def test_second_worker_is_standby_while_dispatch_lease_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            first_adapter = WaitingAdapter()
            second_adapter = WaitingAdapter()
            first_store = StateStore(path)
            first = WorkerHost(
                PersistentFactoryOrchestrator(load_registry(), first_store, AdapterRegistry({"obrasignal": first_adapter})),
                poll_seconds=0, owner_id="worker-a", lease_ttl_seconds=30,
            )
            second = WorkerHost(
                PersistentFactoryOrchestrator(load_registry(), StateStore(path), AdapterRegistry({"obrasignal": second_adapter})),
                poll_seconds=0, owner_id="worker-b", lease_ttl_seconds=30,
            )
            first_result = first.run_once()
            second_result = second.run_once()
            self.assertNotEqual(first_result["global_state"], "STANDBY")
            self.assertEqual(second_result["global_state"], "STANDBY")
            self.assertEqual(second_result["dispatches"], [])
            self.assertEqual(second_adapter.calls, 0)
            self.assertEqual(first_store.lease(LEASE_NAME)["owner_id"], "worker-a")
            first.stop()
            takeover = second.run_once()
            self.assertNotEqual(takeover["global_state"], "STANDBY")
            second.stop()

    def test_standby_worker_does_not_mark_live_execution_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            active_store = StateStore(path)
            active_orchestrator = PersistentFactoryOrchestrator(load_registry(), active_store)
            self.assertTrue(active_store.acquire_or_renew_lease(LEASE_NAME, "worker-a", 30))
            task = active_store.get_app("obrasignal")["active"]
            active_store.start_execution(
                "obrasignal", "live-execution", task,
                {"execution_id": "live-execution", "task": task, "app_id": "obrasignal"},
            )

            standby = WorkerHost(
                PersistentFactoryOrchestrator(load_registry(), StateStore(path)),
                poll_seconds=0, owner_id="worker-b", lease_ttl_seconds=30,
            )
            result = standby.run_once()

            self.assertEqual(result["global_state"], "STANDBY")
            live = active_store.get_app("obrasignal")
            self.assertEqual(live["state"], "EXECUTING")
            self.assertEqual(live["current_execution"]["execution_id"], "live-execution")
            history = active_store.history("obrasignal")
            self.assertEqual(history[0]["status"], "EXECUTING")
            self.assertIsNone(history[0]["finished_at"])
            active_store.release_lease(LEASE_NAME, "worker-a")

    def test_stop_prevents_another_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "state.sqlite3")
            orchestrator = PersistentFactoryOrchestrator(load_registry(), store)
            host = WorkerHost(orchestrator, poll_seconds=0, sleeper=lambda _: None, owner_id="worker-a")
            host.stop()
            self.assertIsNone(host.run_forever())
            self.assertEqual(store.history("obrasignal"), [])


if __name__ == "__main__":
    unittest.main()
