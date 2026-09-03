import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.app_worker import AppWorkerHost
from factory_cloud.capabilities import Capability
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.process_adapter import ProcessAdapterConfig, ProcessAgentAdapter
from factory_cloud.state_store import StateStore, utc_now
from factory_cloud.work_queue import QueuedAppAdapter, open_app_queue


AGENT_PATH = Path(__file__).with_name("repository_mutation_agent.py").resolve()
TASK_1 = "canary:add-endpoint"
TASK_2 = "canary:add-schema"
CAPS = frozenset({
    Capability.READ_REPOSITORY,
    Capability.CREATE_BRANCH,
    Capability.WRITE_FILES,
    Capability.RUN_TESTS,
    Capability.UPDATE_BATON,
})
CAP_VALUES = [item.value for item in sorted(CAPS, key=lambda item: item.value)]


def git(root: Path, *args: str):
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def make_canary(root: Path):
    repo = root / "canary-a"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "canary@example.invalid")
    git(repo, "config", "user.name", "Factory Cloud Canary")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (repo / "app.py").write_text("def health():\n    return {'status': 'ok'}\n", encoding="utf-8")
    (repo / "test_app.py").write_text("from app import health\n\ndef test_health():\n    assert health() == {'status': 'ok'}\n", encoding="utf-8")
    git(repo, "add", ".gitignore", "app.py", "test_app.py")
    git(repo, "commit", "-m", "seed canary")
    git(repo, "branch", "-M", "main")
    return repo, git(repo, "rev-parse", "HEAD").stdout.strip()


def write_runtime_files(root: Path, repo: Path):
    catalog = root / "canary-tasks.json"
    catalog.write_text(json.dumps({
        "tasks": {
            TASK_1: {
                "work_branch": "factory-cloud/canary-a/add-endpoint",
                "writes": [
                    {"path": "app.py", "content": "def health():\n    return {'status': 'ok'}\n\ndef add(a, b):\n    return a + b\n"},
                    {"path": "test_app.py", "content": "from app import add, health\n\ndef test_health():\n    assert health() == {'status': 'ok'}\n\ndef test_add():\n    assert add(2, 3) == 5\n"}
                ],
                "tests": ["python"],
                "commit_message": "canary: add endpoint",
                "publish": False
            },
            TASK_2: {
                "work_branch": "factory-cloud/canary-a/add-schema",
                "writes": [
                    {"path": "app.py", "content": "SCHEMA_VERSION = 2\n\ndef health():\n    return {'status': 'ok'}\n\ndef add(a, b):\n    return a + b\n"},
                    {"path": "test_app.py", "content": "from app import SCHEMA_VERSION, add, health\n\ndef test_health():\n    assert health() == {'status': 'ok'}\n\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_schema():\n    assert SCHEMA_VERSION == 2\n"}
                ],
                "tests": ["python"],
                "commit_message": "canary: add schema",
                "publish": False
            }
        }
    }), encoding="utf-8")
    config = root / "canary-agent.json"
    config.write_text(json.dumps({
        "app_id": "canary-a",
        "repository": "local/canary-a",
        "workspace": str(repo.resolve()),
        "canonical_branch": "main",
        "allowed_branch_prefix": "factory-cloud/canary-a/",
        "task_catalog": str(catalog.resolve()),
        "test_commands": {"python": [sys.executable, "-m", "pytest", "-q"]},
        "capabilities": CAP_VALUES,
        "timeout_seconds": 60
    }), encoding="utf-8")
    return config


def registry(head: str):
    return {
        "activation_code": "D",
        "registry_scope": "application_development_only",
        "applications": [{
            "app_id": "canary-a",
            "name": "Factory Cloud Canary A",
            "kind": "application",
            "mission": "Prove autonomous repository mutation and baton continuation",
            "development_state": "ACTIVE",
            "source_truth": {
                "provider": "local-git-fixture",
                "repository": "local/canary-a",
                "canonical_branch": "main",
                "canonical_head": head,
                "verified": True
            },
            "execution_source": {
                "provider": "local-git-fixture",
                "repository": "local/canary-a",
                "branch": "main",
                "head": head,
                "verified": True
            },
            "execution_adapter": {
                "kind": "repository_mutation_canary",
                "configured": True,
                "allowlisted_tasks": [TASK_1, TASK_2],
                "capabilities": CAP_VALUES,
                "repository_mutation_capability": True
            },
            "task_capabilities": {TASK_1: CAP_VALUES, TASK_2: CAP_VALUES},
            "baton": {"active": TASK_1, "next": [TASK_1, TASK_2], "wait": []},
            "activation": {"enabled": True, "mode": "repository_safe_execution", "priority": 100}
        }]
    }


class LocalVerifiedQueueAdapter:
    """Read-only source check before creating a new durable queue job."""

    def __init__(self, repo: Path, delegate):
        self.repo = repo
        self.delegate = delegate

    def execute(self, request):
        existing = next(
            (job for job in self.delegate.queue.jobs(request.app_id) if job["task"] == request.task and job["consumed_at"] is None),
            None,
        )
        if existing is None:
            observed = git(self.repo, "rev-parse", "HEAD").stdout.strip()
            if request.source != "local/canary-a" or observed != request.target_head:
                return ExecutionResult(
                    status="WAIT",
                    evidence={"source_verification": "MISMATCH", "observed_head": observed},
                    next_active=request.task,
                    blockers=("source_mismatch",),
                    resume_at=request.task,
                    last_verified=utc_now(),
                )
        result = self.delegate.execute(request)
        return ExecutionResult(
            status=result.status,
            evidence={**result.evidence, "source_verification": "VERIFIED"},
            next_active=result.next_active,
            next_items=result.next_items,
            wait_items=result.wait_items,
            blockers=result.blockers,
            resume_at=result.resume_at,
            last_verified=utc_now(),
            last_green=result.last_green,
            execution_branch=result.execution_branch,
            execution_head=result.execution_head,
            error=result.error,
        )


class FactoryCloudPrivateQueueCanaryAcceptanceTests(unittest.TestCase):
    def test_two_real_repository_tasks_survive_control_restart_on_private_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, canonical_head = make_canary(root)
            agent_config = write_runtime_files(root, repo)
            state_path = root / "control" / "state.sqlite3"
            queue_root = root / "queues"
            store = StateStore(state_path)
            queue = open_app_queue(queue_root, "canary-a")
            reg = registry(canonical_head)

            self.assertNotEqual(queue.store.path, state_path)
            with sqlite3.connect(state_path) as conn:
                self.assertIsNone(conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='worker_jobs'"
                ).fetchone())

            control = PersistentFactoryOrchestrator(
                reg,
                store,
                AdapterRegistry({"canary-a": LocalVerifiedQueueAdapter(repo, QueuedAppAdapter(queue))}),
            )
            process_config = ProcessAdapterConfig(
                app_id="canary-a",
                mode="repository_safe_execution",
                workspace=repo,
                command=(sys.executable, str(AGENT_PATH), "--config", str(agent_config)),
                capabilities=CAPS,
                timeout_seconds=60,
            )
            app_worker = AppWorkerHost(
                "canary-a",
                queue,
                adapters=AdapterRegistry({"canary-a": ProcessAgentAdapter(process_config)}),
                worker_id="canary-worker",
                poll_seconds=0,
                job_lease_seconds=30,
            )

            first_control = control.run_cycle(max_dispatches=1)
            self.assertEqual([item["status"] for item in first_control["dispatches"]], ["WAIT"])
            self.assertEqual(queue.jobs()[0]["task"], TASK_1)
            first_worker = app_worker.run_once()
            self.assertEqual(first_worker["state"], "DONE")
            first_head = first_worker["result"]["execution_head"]
            self.assertNotEqual(first_head, canonical_head)

            restarted_store = StateStore(state_path)
            restarted_queue = open_app_queue(queue_root, "canary-a")
            restarted_control = PersistentFactoryOrchestrator(
                reg,
                restarted_store,
                AdapterRegistry({"canary-a": LocalVerifiedQueueAdapter(repo, QueuedAppAdapter(restarted_queue))}),
                recover_interrupted=True,
            )
            after_restart = restarted_control.run_cycle(max_dispatches=2)
            self.assertEqual([item["status"] for item in after_restart["dispatches"]], ["DONE", "WAIT"])
            state = restarted_store.get_app("canary-a")
            self.assertEqual(state["canonical_head"], canonical_head)
            self.assertEqual(state["execution_head"], first_head)
            self.assertEqual(state["active"], TASK_2)
            self.assertEqual(state["resume_at"], TASK_2)
            jobs = restarted_queue.jobs()
            self.assertEqual([job["task"] for job in jobs], [TASK_1, TASK_2])
            self.assertEqual(jobs[1]["request"]["execution_head"], first_head)

            second_worker = AppWorkerHost(
                "canary-a",
                restarted_queue,
                adapters=AdapterRegistry({"canary-a": ProcessAgentAdapter(process_config)}),
                worker_id="canary-worker-2",
                poll_seconds=0,
                job_lease_seconds=30,
            )
            second_result = second_worker.run_once()
            self.assertEqual(second_result["state"], "DONE")
            second_head = second_result["result"]["execution_head"]
            self.assertNotEqual(second_head, first_head)

            final = restarted_control.run_cycle(max_dispatches=2)
            self.assertEqual([item["status"] for item in final["dispatches"]], ["DONE"])
            final_state = restarted_store.get_app("canary-a")
            self.assertEqual(final_state["canonical_head"], canonical_head)
            self.assertEqual(final_state["execution_head"], second_head)
            self.assertEqual(final_state["execution_branch"], "factory-cloud/canary-a/add-schema")
            self.assertEqual(final_state["active"], "")
            self.assertEqual(final_state["resume_at"], TASK_2)
            self.assertFalse(final_state["blockers"])

            completed_jobs = restarted_queue.jobs()
            self.assertEqual(len(completed_jobs), 2)
            self.assertTrue(all(job["status"] == "DONE" and job["consumed_at"] for job in completed_jobs))
            self.assertEqual(git(repo, "rev-parse", "HEAD").stdout.strip(), second_head)
            self.assertEqual(git(repo, "status", "--porcelain").stdout, "")
            self.assertIn("SCHEMA_VERSION = 2", (repo / "app.py").read_text(encoding="utf-8"))

            history = restarted_store.history("canary-a", limit=20)
            self.assertGreaterEqual(sum(1 for item in history if item["status"] == "DONE"), 2)
            self.assertFalse(any(item["status"] == "ERROR" for item in history))


if __name__ == "__main__":
    unittest.main()
