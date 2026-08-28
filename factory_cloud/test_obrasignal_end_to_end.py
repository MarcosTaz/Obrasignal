import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import AdapterRegistry
from factory_cloud.app_worker import AppWorkerHost
from factory_cloud.capabilities import Capability
from factory_cloud.obrasignal_agent import AGENT_CAPABILITIES, TASK_COMPILE, TASK_PYTHON
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.process_adapter import ProcessAdapterConfig, ProcessAgentAdapter
from factory_cloud.state_store import StateStore, utc_now
from factory_cloud.verification import SourceVerification, VerifiedDispatchAdapter
from factory_cloud.work_queue import DurableWorkQueue, QueuedAppAdapter
from factory_cloud.worker import WorkerHost


AGENT_PATH = Path(__file__).with_name("obrasignal_agent.py").resolve()
EXECUTION_BRANCH = "integration/current-spine"
CAPABILITY_VALUES = [item.value for item in sorted(AGENT_CAPABILITIES, key=lambda item: item.value)]


class StaticVerifiedHead:
    def __init__(self, head, branch):
        self.head = head
        self.branch = branch

    def verify(self, repository, branch, expected_head):
        if branch != self.branch or expected_head != self.head:
            raise AssertionError("test execution source and workspace head diverged")
        return SourceVerification(
            status="VERIFIED",
            verified_at=utc_now(),
            expected_head=expected_head,
            observed_head=self.head,
            evidence={"repository": repository, "branch": branch, "head": self.head},
        )


def _run(argv, cwd):
    return subprocess.run(
        list(argv),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


def _git_workspace(root):
    workspace = root / "obrasignal-workspace"
    workspace.mkdir()
    _run(("git", "init"), workspace)
    _run(("git", "config", "user.email", "factory-cloud-test@example.invalid"), workspace)
    _run(("git", "config", "user.name", "Factory Cloud Test"), workspace)
    (workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _run(("git", "add", "app.py"), workspace)
    _run(("git", "commit", "-m", "seed canonical main"), workspace)
    _run(("git", "branch", "-M", "main"), workspace)
    canonical_head = _run(("git", "rev-parse", "HEAD"), workspace).stdout.strip()

    _run(("git", "checkout", "-b", EXECUTION_BRANCH), workspace)
    (workspace / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run(("git", "add", "app.py"), workspace)
    _run(("git", "commit", "-m", "seed noncanonical development candidate"), workspace)
    execution_head = _run(("git", "rev-parse", "HEAD"), workspace).stdout.strip()
    return workspace, canonical_head, execution_head


def _registry(canonical_head, execution_head):
    return {
        "activation_code": "Ω",
        "registry_scope": "application_development_only",
        "applications": [
            {
                "app_id": "obrasignal",
                "name": "ObraSignal",
                "kind": "application",
                "mission": "End-to-end verification acceptance fixture",
                "development_state": "ACTIVE",
                "source_truth": {
                    "provider": "github",
                    "repository": "MarcosTaz/Obrasignal",
                    "canonical_branch": "main",
                    "canonical_head": canonical_head,
                    "verified": True,
                },
                "execution_source": {
                    "provider": "github",
                    "repository": "MarcosTaz/Obrasignal",
                    "branch": EXECUTION_BRANCH,
                    "head": execution_head,
                    "verified": True,
                },
                "execution_adapter": {
                    "kind": "test-verification-adapter",
                    "configured": True,
                    "allowlisted_tasks": [TASK_COMPILE, TASK_PYTHON],
                    "capabilities": list(CAPABILITY_VALUES),
                    "repository_mutation_capability": False,
                },
                "task_capabilities": {
                    TASK_COMPILE: list(CAPABILITY_VALUES),
                    TASK_PYTHON: list(CAPABILITY_VALUES),
                },
                "baton": {
                    "active": TASK_COMPILE,
                    "next": [TASK_COMPILE, TASK_PYTHON],
                    "wait": ["repository mutation remains unauthorized"],
                },
                "activation": {
                    "enabled": True,
                    "mode": "repository_safe_execution",
                    "priority": 100,
                },
            }
        ],
    }


class ObraSignalEndToEndTests(unittest.TestCase):
    def test_compile_baton_executes_verified_noncanonical_source_without_promoting_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, canonical_head, execution_head = _git_workspace(root)
            self.assertNotEqual(canonical_head, execution_head)
            store = StateStore(root / "factory-cloud.sqlite3")
            queue = DurableWorkQueue(store)
            registry = _registry(canonical_head, execution_head)

            queued = QueuedAppAdapter(queue)
            verified = VerifiedDispatchAdapter(
                queued,
                repository="MarcosTaz/Obrasignal",
                branch=EXECUTION_BRANCH,
                expected_head=execution_head,
                verifier=StaticVerifiedHead(execution_head, EXECUTION_BRANCH),
            )
            control = PersistentFactoryOrchestrator(
                registry,
                store,
                adapters=AdapterRegistry({"obrasignal": verified}),
                recover_interrupted=False,
            )
            control_host = WorkerHost(
                control,
                poll_seconds=0,
                max_dispatches_per_cycle=1,
                owner_id="control-e2e",
                lease_ttl_seconds=30,
            )

            first = control_host.run_once()
            self.assertEqual(first["dispatches"][0]["status"], "WAIT")
            jobs = queue.jobs("obrasignal")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["status"], "QUEUED")
            self.assertEqual(jobs[0]["task"], TASK_COMPILE)
            self.assertEqual(jobs[0]["request"]["canonical_head"], canonical_head)
            self.assertEqual(jobs[0]["request"]["execution_branch"], EXECUTION_BRANCH)
            self.assertEqual(jobs[0]["request"]["execution_head"], execution_head)
            self.assertEqual(jobs[0]["request"]["required_capabilities"], CAPABILITY_VALUES)

            self.assertEqual(store.get_app("obrasignal")["canonical_head"], canonical_head)

            process_config = ProcessAdapterConfig(
                app_id="obrasignal",
                mode="repository_safe_execution",
                workspace=workspace,
                command=(sys.executable, str(AGENT_PATH)),
                capabilities=AGENT_CAPABILITIES,
                timeout_seconds=60,
            )
            app_host = AppWorkerHost(
                "obrasignal",
                queue,
                adapters=AdapterRegistry({"obrasignal": ProcessAgentAdapter(process_config)}),
                worker_id="obrasignal-e2e",
                poll_seconds=0,
                job_lease_seconds=30,
            )
            worker_result = app_host.run_once()
            self.assertEqual(worker_result["state"], "DONE")
            self.assertEqual(worker_result["result"]["evidence"]["verified_head"], execution_head)
            self.assertEqual(worker_result["result"]["evidence"]["test_state"], "SUCCESS")
            self.assertEqual(worker_result["result"]["evidence"]["evidence_codes"], ["compile_green"])

            completed = queue.jobs("obrasignal")
            self.assertEqual(completed[0]["status"], "DONE")
            self.assertIsNone(completed[0]["consumed_at"])

            second = control_host.run_once()
            self.assertEqual(second["dispatches"][0]["status"], "DONE")
            state = store.get_app("obrasignal")
            self.assertEqual(state["active"], TASK_PYTHON)
            self.assertEqual(state["resume_at"], TASK_PYTHON)
            self.assertEqual(state["canonical_head"], canonical_head)
            self.assertEqual(state["last_green"], execution_head)
            self.assertFalse(state["blockers"])

            consumed = queue.jobs("obrasignal")
            self.assertIsNotNone(consumed[0]["consumed_at"])
            history = store.history("obrasignal")
            statuses = [item["status"] for item in history]
            self.assertIn("DONE", statuses)
            self.assertIn("WAIT", statuses)

            self.assertEqual(_run(("git", "rev-parse", "HEAD"), workspace).stdout.strip(), execution_head)
            self.assertEqual(_run(("git", "status", "--porcelain"), workspace).stdout, "")


if __name__ == "__main__":
    unittest.main()
