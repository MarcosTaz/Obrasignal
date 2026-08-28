import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import STATE_SCHEMA_VERSION, StateStore


CANONICAL = "a" * 40
INITIAL_EXECUTION = "b" * 40
NEXT_EXECUTION = "c" * 40


def registry():
    return {
        "activation_code": "Ω",
        "registry_scope": "application_development_only",
        "applications": [{
            "app_id": "canary-a",
            "name": "Canary A",
            "kind": "application",
            "mission": "prove mutable execution source durability",
            "development_state": "ACTIVE",
            "source_truth": {
                "provider": "github",
                "repository": "local/canary-a",
                "canonical_branch": "main",
                "canonical_head": CANONICAL,
                "verified": True,
            },
            "execution_source": {
                "provider": "github",
                "repository": "local/canary-a",
                "branch": "integration/base",
                "head": INITIAL_EXECUTION,
                "verified": True,
            },
            "task_capabilities": {"mutate:first": [], "mutate:second": []},
            "baton": {"active": "mutate:first", "next": ["mutate:second"], "wait": []},
            "activation": {"enabled": True, "mode": "repository_safe_execution", "priority": 100},
        }],
    }


class AdvancingAdapter:
    def execute(self, request):
        return ExecutionResult(
            status="DONE",
            evidence={"commit_sha": NEXT_EXECUTION, "test_state": "SUCCESS"},
            last_verified=NEXT_EXECUTION,
            last_green=NEXT_EXECUTION,
            execution_branch="factory-cloud/canary-a/first",
            execution_head=NEXT_EXECUTION,
        )


class CanonicalBranchAdapter:
    def execute(self, request):
        return ExecutionResult(
            status="DONE",
            evidence={"commit_sha": NEXT_EXECUTION, "test_state": "SUCCESS"},
            execution_branch="main",
            execution_head=NEXT_EXECUTION,
        )


class ExecutionSourceStateTests(unittest.TestCase):
    def test_done_advances_only_execution_source_and_restart_keeps_new_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cloud.sqlite3"
            store = StateStore(path)
            cloud = PersistentFactoryOrchestrator(registry(), store, AdapterRegistry({"canary-a": AdvancingAdapter()}))
            result = cloud.run_cycle(max_dispatches=1)
            self.assertEqual(result["dispatches"][0]["status"], "DONE")

            state = store.get_app("canary-a")
            self.assertEqual(state["canonical_head"], CANONICAL)
            self.assertEqual(state["execution_branch"], "factory-cloud/canary-a/first")
            self.assertEqual(state["execution_head"], NEXT_EXECUTION)
            self.assertEqual(state["active"], "mutate:second")
            self.assertEqual(state["resume_at"], "mutate:second")

            restarted = PersistentFactoryOrchestrator(registry(), StateStore(path))
            recovered = restarted.store.get_app("canary-a")
            self.assertEqual(recovered["canonical_head"], CANONICAL)
            self.assertEqual(recovered["execution_head"], NEXT_EXECUTION)
            decision = restarted.choose_next()
            self.assertEqual(decision.execution_head, NEXT_EXECUTION)
            self.assertEqual(decision.execution_branch, "factory-cloud/canary-a/first")

    def test_adapter_cannot_smuggle_done_mutation_onto_canonical_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "cloud.sqlite3")
            cloud = PersistentFactoryOrchestrator(registry(), store, AdapterRegistry({"canary-a": CanonicalBranchAdapter()}))
            result = cloud.run_cycle(max_dispatches=1)
            self.assertEqual(result["dispatches"][0]["status"], "ERROR")
            state = store.get_app("canary-a")
            self.assertEqual(state["canonical_head"], CANONICAL)
            self.assertEqual(state["execution_head"], INITIAL_EXECUTION)
            self.assertEqual(state["active"], "mutate:first")
            history = store.history("canary-a")
            self.assertEqual(history[0]["status"], "ERROR")
            self.assertEqual(history[0]["error"]["type"], "CANONICAL_BRANCH_MUTATION_REJECTED")

    def test_v2_app_state_is_migrated_in_place_without_losing_baton(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cloud.sqlite3"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE factory_cloud_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO factory_cloud_meta(key,value) VALUES('schema_version','2')")
            conn.execute(
                """CREATE TABLE app_state (
                    app_id TEXT PRIMARY KEY, mission TEXT NOT NULL DEFAULT '', repo_source TEXT,
                    canonical_head TEXT, runtime TEXT, state TEXT NOT NULL, active TEXT NOT NULL DEFAULT '',
                    next_json TEXT NOT NULL DEFAULT '[]', wait_json TEXT NOT NULL DEFAULT '[]',
                    blockers_json TEXT NOT NULL DEFAULT '[]', last_verified TEXT, last_green TEXT,
                    priority INTEGER NOT NULL DEFAULT 0, resume_at TEXT NOT NULL DEFAULT '',
                    current_execution_json TEXT, error_state_json TEXT,
                    retry_state_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """INSERT INTO app_state(app_id,mission,repo_source,canonical_head,runtime,state,active,next_json,
                   wait_json,blockers_json,last_verified,last_green,priority,resume_at,current_execution_json,
                   error_state_json,retry_state_json,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("legacy", "legacy mission", "owner/repo", CANONICAL, "github", "READY", "legacy-task",
                 json.dumps(["next-task"]), "[]", "[]", None, None, 1, "legacy-task", None, None, "{}", "2026-08-28T00:00:00+00:00"),
            )
            conn.commit()
            conn.close()

            store = StateStore(path)
            state = store.get_app("legacy")
            self.assertEqual(state["active"], "legacy-task")
            self.assertEqual(state["next"], ["next-task"])
            self.assertIsNone(state["execution_branch"])
            self.assertIsNone(state["execution_head"])
            with store.connection() as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(app_state)")}
                version = conn.execute("SELECT value FROM factory_cloud_meta WHERE key='schema_version'").fetchone()[0]
            self.assertIn("execution_branch", columns)
            self.assertIn("execution_head", columns)
            self.assertEqual(version, str(STATE_SCHEMA_VERSION))


if __name__ == "__main__":
    unittest.main()
