import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore


class StaleResumeDoneAdapter:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return ExecutionResult(
            status="DONE",
            evidence={"test_state": "SUCCESS"},
            resume_at=request.task,
        )


class DoneResumeAtTests(unittest.TestCase):
    def test_done_cannot_leave_resume_at_on_completed_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "cloud.sqlite3")
            adapter = StaleResumeDoneAdapter()
            cloud = PersistentFactoryOrchestrator(
                load_registry(),
                store,
                AdapterRegistry({"obrasignal": adapter}),
            )
            before = store.get_app("obrasignal")
            completed = before["active"]
            expected_next = before["next"][1] if before["next"] and before["next"][0] == completed else before["next"][0]

            result = cloud.run_cycle(max_dispatches=1)
            self.assertEqual(result["dispatches"][0]["status"], "DONE")
            after = store.get_app("obrasignal")
            self.assertNotEqual(after["active"], completed)
            self.assertEqual(after["active"], expected_next)
            self.assertEqual(after["resume_at"], after["active"])


if __name__ == "__main__":
    unittest.main()
