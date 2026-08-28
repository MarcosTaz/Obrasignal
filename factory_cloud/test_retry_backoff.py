from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore
from factory_cloud.work_queue import DurableWorkQueue, QueuedAppAdapter


class ErrorAdapter:
    def execute(self, request):
        return ExecutionResult(
            status="ERROR",
            next_active=request.task,
            blockers=("deterministic_test_error",),
            resume_at=request.task,
            error={"type": "TEST_ERROR"},
        )


class RetryBackoffTests(unittest.TestCase):
    @staticmethod
    def _obrasignal_decision(cloud):
        return cloud._decision_for(cloud.store.get_app("obrasignal"))

    def test_pending_worker_wait_does_not_delay_consumption_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "cloud.sqlite3")
            queue = DurableWorkQueue(store)
            cloud = PersistentFactoryOrchestrator(
                load_registry(),
                store,
                AdapterRegistry({"obrasignal": QueuedAppAdapter(queue)}),
            )

            result = cloud.run_cycle(max_dispatches=1)
            self.assertEqual(result["dispatches"][0]["status"], "WAIT")
            self.assertIn("app_worker_execution_pending", store.get_app("obrasignal")["blockers"])
            self.assertNotIn("next_attempt_at", store.get_app("obrasignal")["retry_state"])
            self.assertIsNotNone(self._obrasignal_decision(cloud))

    def test_error_retry_gate_survives_orchestrator_restart_and_expires_by_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cloud.sqlite3"
            store = StateStore(path)
            registry = load_registry()
            cloud = PersistentFactoryOrchestrator(
                registry,
                store,
                AdapterRegistry({"obrasignal": ErrorAdapter()}),
            )

            result = cloud.run_cycle(max_dispatches=1)
            self.assertEqual(result["dispatches"][0]["status"], "ERROR")
            state = store.get_app("obrasignal")
            retry = state["retry_state"]
            self.assertEqual(retry["task"], state["active"])
            self.assertEqual(retry["retry_reason"], "ERROR")
            self.assertEqual(retry["attempts"], 1)
            self.assertGreater(datetime.fromisoformat(retry["next_attempt_at"]), datetime.now(timezone.utc))

            restarted = PersistentFactoryOrchestrator(registry, StateStore(path))
            self.assertIsNone(self._obrasignal_decision(restarted))

            retry["next_attempt_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            restarted.store.checkpoint("obrasignal", retry_state_json=retry)
            decision = self._obrasignal_decision(restarted)
            self.assertIsNotNone(decision)
            self.assertEqual(decision.task, state["active"])

    def test_retry_gate_is_task_scoped_and_cannot_block_a_new_active_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "cloud.sqlite3")
            registry = load_registry()
            cloud = PersistentFactoryOrchestrator(
                registry,
                store,
                AdapterRegistry({"obrasignal": ErrorAdapter()}),
            )
            cloud.run_cycle(max_dispatches=1)
            state = store.get_app("obrasignal")
            old_task = state["active"]
            new_task = "safe-new-task-after-owner-change"
            self.assertNotEqual(old_task, new_task)

            store.checkpoint("obrasignal", active=new_task, resume_at=new_task)
            decision = self._obrasignal_decision(cloud)
            self.assertIsNotNone(decision)
            self.assertEqual(decision.task, new_task)

    def test_malformed_same_task_retry_timestamp_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "cloud.sqlite3")
            cloud = PersistentFactoryOrchestrator(load_registry(), store)
            task = store.get_app("obrasignal")["active"]
            store.checkpoint(
                "obrasignal",
                retry_state_json={"task": task, "next_attempt_at": "not-a-time", "retry_reason": "WAIT"},
            )
            self.assertIsNone(self._obrasignal_decision(cloud))


if __name__ == "__main__":
    unittest.main()
