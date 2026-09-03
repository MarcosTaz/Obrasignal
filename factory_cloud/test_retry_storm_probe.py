import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.app_worker import AppWorkerHost
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore
from factory_cloud.work_queue import DurableWorkQueue, QueuedAppAdapter


class AlwaysWaitAdapter:
    def execute(self, request):
        return ExecutionResult(
            status="WAIT",
            evidence={"task_state": "dependency_unavailable"},
            next_active=request.task,
            blockers=("dependency_unavailable",),
            resume_at=request.task,
        )


class RetryStormProbeTests(unittest.TestCase):
    def test_terminal_wait_does_not_immediately_create_an_identical_new_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "cloud.sqlite3")
            registry = load_registry()
            queue = DurableWorkQueue(store)
            control = PersistentFactoryOrchestrator(
                registry,
                store,
                adapters=AdapterRegistry({"obrasignal": QueuedAppAdapter(queue)}),
            )

            # First control dispatch creates the app-scoped job.
            first = control.run_cycle(max_dispatches=1)
            self.assertEqual(first["dispatches"][0]["status"], "WAIT")
            self.assertEqual(len(queue.jobs("obrasignal")), 1)

            # App worker returns a durable terminal WAIT for the same ACTIVE task.
            app = AppWorkerHost(
                "obrasignal",
                queue,
                adapters=AdapterRegistry({"obrasignal": AlwaysWaitAdapter()}),
                worker_id="wait-probe",
                poll_seconds=0,
                job_lease_seconds=30,
            )
            self.assertEqual(app.run_once()["state"], "WAIT")

            # Next control cycle consumes the terminal WAIT.
            consumed = control.run_cycle(max_dispatches=1)
            self.assertEqual(consumed["dispatches"][0]["status"], "WAIT")
            self.assertEqual(len(queue.jobs("obrasignal")), 1)

            # An immediately following cycle may legitimately yield to another app,
            # but ObraSignal itself must not be re-queued while its unchanged WAIT
            # retry gate is closed.
            immediate = control.run_cycle(max_dispatches=1)
            self.assertFalse(any(item["app_id"] == "obrasignal" for item in immediate["dispatches"]))
            self.assertEqual(len(queue.jobs("obrasignal")), 1)
            obra_state = store.get_app("obrasignal")
            self.assertEqual(obra_state["active"], obra_state["retry_state"]["task"])
            self.assertEqual(obra_state["retry_state"]["retry_reason"], "WAIT")
            self.assertIn("next_attempt_at", obra_state["retry_state"])


if __name__ == "__main__":
    unittest.main()
