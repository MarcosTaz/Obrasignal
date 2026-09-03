import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.control_plane import load_registry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore


SENSITIVE_SENTINEL = "credential-like-sentinel-must-not-persist"


class ScriptedAdapter:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        if not self.results:
            return ExecutionResult(status="WAIT", blockers=("script_exhausted",), resume_at=request.task)
        return self.results.pop(0)


class ExplodingAdapter:
    def execute(self, request):
        raise RuntimeError(SENSITIVE_SENTINEL)


class FactoryCloudPersistentOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / "cloud.sqlite3"
        self.registry = load_registry()

    def tearDown(self):
        self.tmp.cleanup()

    def test_registry_recovers_each_application_into_durable_state(self):
        store = StateStore(self.state_path)
        PersistentFactoryOrchestrator(self.registry, store)
        states = {item["app_id"]: item for item in store.list_apps()}
        self.assertEqual(set(states), {"obrasignal", "k3-fatality"})
        required = {
            "app_id", "mission", "repo_source", "canonical_head", "runtime", "state",
            "active", "next", "wait", "blockers", "last_verified", "last_green",
            "priority", "resume_at", "current_execution", "error_state", "retry_state", "updated_at",
        }
        self.assertTrue(required.issubset(states["obrasignal"]))
        self.assertEqual(states["obrasignal"]["repo_source"], "MarcosTaz/Obrasignal")
        self.assertIsNone(states["k3-fatality"]["canonical_head"])

    def test_done_persists_then_immediately_advances_to_next_task(self):
        adapter = ScriptedAdapter([
            ExecutionResult(status="DONE", evidence={"gate": "green"}),
            ExecutionResult(status="WAIT", evidence={"boundary": "owner"}, blockers=("owner_boundary",)),
        ])
        store = StateStore(self.state_path)
        cloud = PersistentFactoryOrchestrator(self.registry, store, AdapterRegistry({"obrasignal": adapter}))
        result = cloud.run_cycle(max_dispatches=2)
        self.assertEqual([d["status"] for d in result["dispatches"]], ["DONE", "WAIT"])
        self.assertEqual(len(adapter.requests), 2)
        self.assertNotEqual(adapter.requests[0].task, adapter.requests[1].task)
        self.assertEqual(store.get_app("obrasignal")["state"], "WAIT")
        self.assertEqual(len(store.history("obrasignal")), 2)

    def test_blocked_app_yields_to_next_eligible_app(self):
        obra = ScriptedAdapter([ExecutionResult(status="WAIT", blockers=("human_authorization",), resume_at="safe resume")])
        k3 = ScriptedAdapter([ExecutionResult(status="WAIT", blockers=("source_unresolved",), resume_at="resolve source")])
        cloud = PersistentFactoryOrchestrator(
            self.registry, StateStore(self.state_path), AdapterRegistry({"obrasignal": obra, "k3-fatality": k3})
        )
        result = cloud.run_cycle(max_dispatches=5)
        self.assertEqual([d["app_id"] for d in result["dispatches"]], ["obrasignal", "k3-fatality"])
        self.assertEqual(result["global_state"], "WAIT")
        self.assertIn("obrasignal", result["blockers"])
        self.assertIn("k3-fatality", result["blockers"])

    def test_process_restart_recovers_interrupted_execution_exactly(self):
        store = StateStore(self.state_path)
        PersistentFactoryOrchestrator(self.registry, store)
        original = store.get_app("obrasignal")
        task = original["active"]
        store.start_execution(
            "obrasignal", "crashed-execution", task,
            {"execution_id": "crashed-execution", "task": task, "app_id": "obrasignal"},
        )
        restarted = PersistentFactoryOrchestrator(
            self.registry, StateStore(self.state_path), recover_interrupted=True
        )
        recovered = restarted.store.get_app("obrasignal")
        self.assertEqual(recovered["state"], "READY")
        self.assertEqual(recovered["active"], task)
        self.assertEqual(recovered["resume_at"], task)
        self.assertIsNone(recovered["current_execution"])
        self.assertEqual(recovered["error_state"]["type"], "PROCESS_INTERRUPTED")
        self.assertEqual(recovered["error_state"]["execution_id"], "crashed-execution")
        self.assertEqual(recovered["retry_state"]["interrupted_count"], 1)
        history = restarted.store.history("obrasignal")
        self.assertEqual(history[0]["execution_id"], "crashed-execution")
        self.assertEqual(history[0]["status"], "INTERRUPTED")
        self.assertIsNotNone(history[0]["finished_at"])
        self.assertEqual(history[0]["error"]["type"], "PROCESS_INTERRUPTED")
        self.assertEqual(history[0]["evidence"]["resume_at"], task)

    def test_adapter_exception_is_fail_closed_and_message_is_not_persisted(self):
        store = StateStore(self.state_path)
        cloud = PersistentFactoryOrchestrator(self.registry, store, AdapterRegistry({"obrasignal": ExplodingAdapter()}))
        result = cloud.run_cycle(max_dispatches=1)
        self.assertEqual(result["dispatches"][0]["status"], "ERROR")
        state = store.get_app("obrasignal")
        self.assertEqual(state["state"], "ERROR")
        self.assertEqual(state["resume_at"], state["active"])
        self.assertEqual(state["error_state"], {"type": "RuntimeError"})
        history = store.history("obrasignal")[0]
        self.assertEqual(history["status"], "ERROR")
        self.assertEqual(history["error"], {"type": "RuntimeError"})
        persisted = str(state) + str(history) + str(result)
        self.assertNotIn(SENSITIVE_SENTINEL, persisted)

    def test_k3_default_adapter_never_claims_repository_mutation_authority(self):
        cloud = PersistentFactoryOrchestrator(self.registry, StateStore(self.state_path))
        result = cloud.run_cycle(max_dispatches=2)
        k3 = next(item for item in result["dispatches"] if item["app_id"] == "k3-fatality")
        self.assertEqual(k3["status"], "WAIT")
        self.assertEqual(k3["evidence"]["dispatch_boundary"], "canonical_source_unresolved")

    def test_state_schema_does_not_store_cross_app_secret_or_production_authority_fields(self):
        store = StateStore(self.state_path)
        with store.connection() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(app_state)")}
        forbidden = {"secret", "credentials", "customer_data", "billing_authority", "deployment_authority"}
        self.assertTrue(columns.isdisjoint(forbidden))


if __name__ == "__main__":
    unittest.main()
