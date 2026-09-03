import sqlite3
import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import ExecutionRequest
from factory_cloud.app_worker import AppWorkerHost
from factory_cloud.state_store import StateStoreError
from factory_cloud.work_queue import QueuedAppAdapter, app_queue_path, open_app_queue


class AppQueueIsolationTests(unittest.TestCase):
    @staticmethod
    def request(app_id: str, task: str) -> ExecutionRequest:
        return ExecutionRequest(
            app_id=app_id,
            mode="repository_safe_execution",
            task=task,
            source=f"local/{app_id}",
            canonical_head="abc123",
            resume_at=task,
        )

    def test_two_apps_have_distinct_physical_queue_databases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_a = open_app_queue(root, "app-a")
            queue_b = open_app_queue(root, "app-b")
            QueuedAppAdapter(queue_a).execute(self.request("app-a", "task-a"))
            QueuedAppAdapter(queue_b).execute(self.request("app-b", "task-b"))
            path_a = app_queue_path(root, "app-a")
            path_b = app_queue_path(root, "app-b")
            self.assertNotEqual(path_a, path_b)
            self.assertTrue(path_a.is_file())
            self.assertTrue(path_b.is_file())
            with sqlite3.connect(path_a) as conn:
                self.assertEqual(conn.execute("SELECT DISTINCT app_id FROM worker_jobs").fetchall(), [("app-a",)])
            with sqlite3.connect(path_b) as conn:
                self.assertEqual(conn.execute("SELECT DISTINCT app_id FROM worker_jobs").fetchall(), [("app-b",)])
            self.assertEqual([item["app_id"] for item in queue_a.jobs()], ["app-a"])
            self.assertEqual([item["app_id"] for item in queue_b.jobs()], ["app-b"])

    def test_scoped_queue_rejects_cross_app_submit_claim_and_enumeration(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue_a = open_app_queue(Path(tmp), "app-a")
            QueuedAppAdapter(queue_a).execute(self.request("app-a", "task-a"))
            with self.assertRaises(StateStoreError):
                QueuedAppAdapter(queue_a).execute(self.request("app-b", "task-b"))
            with self.assertRaises(StateStoreError):
                queue_a.claim("app-b", "worker-b")
            with self.assertRaises(StateStoreError):
                queue_a.jobs("app-b")
            self.assertEqual([item["app_id"] for item in queue_a.jobs()], ["app-a"])

    def test_worker_refuses_queue_bound_to_another_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue_a = open_app_queue(Path(tmp), "app-a")
            with self.assertRaises(ValueError):
                AppWorkerHost("app-b", queue_a, poll_seconds=0)

    def test_queue_path_rejects_traversal_and_empty_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for app_id in ("", "../app-b", "app/b", "app\\b", "."):
                with self.subTest(app_id=app_id):
                    with self.assertRaises(StateStoreError):
                        app_queue_path(root, app_id)


if __name__ == "__main__":
    unittest.main()
