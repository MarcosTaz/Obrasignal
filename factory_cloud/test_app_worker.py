import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionRequest, ExecutionResult
from factory_cloud.app_worker import AppWorkerHost
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore
from factory_cloud.work_queue import DurableWorkQueue, QueuedAppAdapter


SENSITIVE_SENTINEL = "app-worker-private-sentinel-must-not-persist"


class DoneAdapter:
    def __init__(self):
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return ExecutionResult(
            status="DONE",
            evidence={"verified_head": request.canonical_head},
            next_active="next safe task",
            resume_at="next safe task",
            last_verified="2026-08-28T00:00:00+00:00",
            last_green=request.canonical_head,
        )


class ExplodingAdapter:
    def execute(self, request):
        raise RuntimeError(SENSITIVE_SENTINEL)


class FactoryCloudAppWorkerTests(unittest.TestCase):
    def _queue(self, tmp):
        store = StateStore(Path(tmp) / "state.sqlite3")
        PersistentFactoryOrchestrator(load_registry(), store)
        return store, DurableWorkQueue(store)

    def test_control_plane_to_app_worker_to_control_plane_roundtrip_is_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, queue = self._queue(tmp)
            request = ExecutionRequest(
                app_id="obrasignal",
                mode="repository_safe_execution",
                task="verify exact source truth",
                source="MarcosTaz/Obrasignal",
                canonical_head="66d43f6fd51cf9cea08016dad335aaa04b711a24",
                resume_at="verify exact source truth",
            )
            dispatch = QueuedAppAdapter(queue)
            pending = dispatch.execute(request)
            self.assertEqual(pending.status, "WAIT")
            self.assertEqual(queue.jobs("obrasignal")[0]["status"], "QUEUED")

            adapter = DoneAdapter()
            app_worker = AppWorkerHost(
                "obrasignal",
                queue,
                AdapterRegistry({"obrasignal": adapter}),
                worker_id="obrasignal-worker-1",
                poll_seconds=0,
            )
            worker_result = app_worker.run_once()
            self.assertEqual(worker_result["state"], "DONE")
            self.assertEqual(adapter.calls, 1)

            completed = dispatch.execute(request)
            self.assertEqual(completed.status, "DONE")
            self.assertEqual(completed.next_active, "next safe task")
            self.assertEqual(completed.evidence["verified_head"], request.canonical_head)
            job = queue.jobs("obrasignal")[0]
            self.assertEqual(job["status"], "DONE")
            self.assertIsNotNone(job["consumed_at"])

            restarted_queue = DurableWorkQueue(StateStore(Path(tmp) / "state.sqlite3"))
            self.assertEqual(restarted_queue.jobs("obrasignal")[0]["status"], "DONE")

    def test_app_worker_can_only_claim_its_own_app_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, queue = self._queue(tmp)
            request = ExecutionRequest(
                app_id="obrasignal", mode="repository_safe_execution", task="safe task",
                source="MarcosTaz/Obrasignal", canonical_head="abc", resume_at="safe task",
            )
            QueuedAppAdapter(queue).execute(request)
            k3_worker = AppWorkerHost("k3-fatality", queue, worker_id="k3-worker", poll_seconds=0)
            result = k3_worker.run_once()
            self.assertEqual(result["state"], "IDLE")
            self.assertEqual(queue.jobs("obrasignal")[0]["status"], "QUEUED")

    def test_default_repo_worker_fails_closed_without_tooling_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, queue = self._queue(tmp)
            request = ExecutionRequest(
                app_id="obrasignal", mode="repository_safe_execution", task="safe task",
                source="MarcosTaz/Obrasignal", canonical_head="abc", resume_at="safe task",
            )
            dispatch = QueuedAppAdapter(queue)
            dispatch.execute(request)
            worker = AppWorkerHost("obrasignal", queue, worker_id="obra-default", poll_seconds=0)
            result = worker.run_once()
            self.assertEqual(result["state"], "WAIT")
            consumed = dispatch.execute(request)
            self.assertEqual(consumed.status, "WAIT")
            self.assertIn("repository_tooling_adapter_required", consumed.blockers)

    def test_app_worker_exception_message_is_not_persisted_in_shared_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, queue = self._queue(tmp)
            request = ExecutionRequest(
                app_id="obrasignal", mode="repository_safe_execution", task="safe task",
                source="MarcosTaz/Obrasignal", canonical_head="abc", resume_at="safe task",
            )
            dispatch = QueuedAppAdapter(queue)
            dispatch.execute(request)
            worker = AppWorkerHost(
                "obrasignal", queue, AdapterRegistry({"obrasignal": ExplodingAdapter()}),
                worker_id="obra-error", poll_seconds=0,
            )
            worker_result = worker.run_once()
            self.assertEqual(worker_result["state"], "ERROR")
            completed = dispatch.execute(request)
            self.assertEqual(completed.error, {"type": "RuntimeError"})
            persisted = str(queue.jobs("obrasignal")) + str(worker_result) + str(completed)
            self.assertNotIn(SENSITIVE_SENTINEL, persisted)


if __name__ == "__main__":
    unittest.main()
