import subprocess
import tempfile
import unittest
from pathlib import Path

from factory_cloud.obrasignal_agent import (
    AGENT_CAPABILITIES,
    ObraSignalVerificationAgent,
    TASK_COMPILE,
    TASK_MOBILE,
    TASK_PYTHON,
    TASK_QUALITY,
)


HEAD = "a" * 40
SENSITIVE = "raw-command-output-must-not-enter-result"
CAPABILITIES = sorted(item.value for item in AGENT_CAPABILITIES)


class FakeRunner:
    def __init__(self, *, head=HEAD, fail_contains=None):
        self.head = head
        self.fail_contains = fail_contains
        self.calls = []

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append((argv, kwargs))
        if argv == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, stdout=self.head + "\n", stderr="")
        joined = " ".join(argv)
        if self.fail_contains and self.fail_contains in joined:
            return subprocess.CompletedProcess(argv, 9, stdout=SENSITIVE, stderr=SENSITIVE)
        return subprocess.CompletedProcess(argv, 0, stdout=SENSITIVE, stderr=SENSITIVE)


class ObraSignalVerificationAgentTests(unittest.TestCase):
    def _payload(self, task):
        return {
            "app_id": "obrasignal",
            "mode": "repository_safe_execution",
            "task": task,
            "source": "MarcosTaz/Obrasignal",
            "canonical_head": HEAD,
            "required_capabilities": list(CAPABILITIES),
            "resume_at": task,
        }

    def _workspace(self, root: Path):
        (root / "tests").mkdir()
        (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "test_root.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    def test_compile_task_needs_no_pytest_or_mobile_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workspace(root)
            runner = FakeRunner()
            agent = ObraSignalVerificationAgent(root, runner=runner, environ={"FACTORY_CLOUD_OBRASIGNAL_PYTHON": "/safe/python"})
            result = agent.execute(self._payload(TASK_COMPILE))

            self.assertEqual(result["status"], "DONE")
            self.assertEqual(result["evidence"]["evidence_codes"], ["compile_green"])
            self.assertEqual(runner.calls[0][0], ["git", "rev-parse", "HEAD"])
            self.assertEqual(runner.calls[1][0][0:2], ["/safe/python", "-c"])
            self.assertIn("compile(", runner.calls[1][0][2])
            self.assertNotIn("py_compile", " ".join(runner.calls[1][0]))
            self.assertFalse(any("pytest" in " ".join(call[0]) for call in runner.calls))
            self.assertFalse(any(call[0] and call[0][0] in {"npm", "npx"} for call in runner.calls))

    def test_python_verification_is_allowlisted_and_uses_fixed_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workspace(root)
            runner = FakeRunner()
            agent = ObraSignalVerificationAgent(root, runner=runner, environ={"FACTORY_CLOUD_OBRASIGNAL_PYTHON": "/safe/python"})
            result = agent.execute(self._payload(TASK_PYTHON))

            self.assertEqual(result["status"], "DONE")
            self.assertEqual(result["evidence"]["test_state"], "SUCCESS")
            self.assertEqual(result["evidence"]["verified_head"], HEAD)
            self.assertEqual(result["last_green"], HEAD)
            self.assertEqual(runner.calls[0][0], ["git", "rev-parse", "HEAD"])
            self.assertEqual(runner.calls[1][0][0:2], ["/safe/python", "-c"])
            self.assertIn("compile(", runner.calls[1][0][2])
            self.assertEqual(runner.calls[2][0][0:5], ["/safe/python", "-m", "pytest", "-q", "--import-mode=importlib"])
            self.assertNotIn("shell", runner.calls[1][1])
            self.assertNotIn(SENSITIVE, str(result))

    def test_unsupported_task_does_not_execute_any_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner()
            result = ObraSignalVerificationAgent(Path(tmp), runner=runner).execute(
                self._payload("git commit -am unsafe")
            )
            self.assertEqual(result["status"], "WAIT")
            self.assertIn("obrasignal_agent_task_not_allowlisted", result["blockers"])
            self.assertEqual(runner.calls, [])

    def test_capability_contract_mismatch_blocks_before_any_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner()
            payload = self._payload(TASK_PYTHON)
            payload["required_capabilities"] = ["READ_REPOSITORY"]
            result = ObraSignalVerificationAgent(Path(tmp), runner=runner).execute(payload)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["evidence"]["task_state"], "AUTHORITY_REQUIRED")
            self.assertIn("obrasignal_agent_capability_contract_mismatch", result["blockers"])
            self.assertEqual(runner.calls, [])

    def test_high_risk_capability_is_invalid_request_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner()
            payload = self._payload(TASK_PYTHON)
            payload["required_capabilities"].append("MERGE_MAIN")
            result = ObraSignalVerificationAgent(Path(tmp), runner=runner).execute(payload)
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["error"], {"type": "INVALID_REQUEST"})
            self.assertEqual(runner.calls, [])

    def test_defense_in_depth_head_mismatch_stops_before_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workspace(root)
            runner = FakeRunner(head="b" * 40)
            result = ObraSignalVerificationAgent(root, runner=runner).execute(self._payload(TASK_PYTHON))
            self.assertEqual(result["status"], "WAIT")
            self.assertIn("local_workspace_head_mismatch", result["blockers"])
            self.assertEqual(len(runner.calls), 1)

    def test_python_failure_is_metadata_only_and_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workspace(root)
            runner = FakeRunner(fail_contains="pytest")
            result = ObraSignalVerificationAgent(root, runner=runner).execute(self._payload(TASK_PYTHON))
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["error"], {"type": "PYTHON_VERIFICATION_FAILED"})
            self.assertEqual(result["resume_at"], TASK_PYTHON)
            self.assertNotIn(SENSITIVE, str(result))

    def test_mobile_without_preinstalled_dependencies_waits_without_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mobile").mkdir()
            runner = FakeRunner()
            result = ObraSignalVerificationAgent(root, runner=runner).execute(self._payload(TASK_MOBILE))
            self.assertEqual(result["status"], "WAIT")
            self.assertIn("mobile_dependencies_required_on_app_workspace", result["blockers"])
            self.assertEqual([call[0] for call in runner.calls], [["git", "rev-parse", "HEAD"]])

    def test_mobile_uses_no_install_and_existing_smoke_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mobile" / "node_modules").mkdir(parents=True)
            runner = FakeRunner()
            result = ObraSignalVerificationAgent(root, runner=runner).execute(self._payload(TASK_MOBILE))
            self.assertEqual(result["status"], "DONE")
            commands = [call[0] for call in runner.calls[1:]]
            self.assertEqual(commands, [
                ["npx", "--no-install", "expo-doctor"],
                ["npm", "run", "smoke:detail"],
                ["npm", "run", "smoke:web"],
            ])
            self.assertNotIn(SENSITIVE, str(result))

    def test_quality_runs_python_then_mobile_and_reports_bounded_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workspace(root)
            (root / "mobile" / "node_modules").mkdir(parents=True)
            runner = FakeRunner()
            result = ObraSignalVerificationAgent(root, runner=runner).execute(self._payload(TASK_QUALITY))
            self.assertEqual(result["status"], "DONE")
            self.assertEqual(result["evidence"]["evidence_codes"], ["python_green", "mobile_green"])
            self.assertEqual(result["evidence"]["commit_sha"], HEAD)

    def test_invalid_request_fails_closed_without_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner()
            payload = self._payload(TASK_PYTHON)
            payload["app_id"] = "k3-fatality"
            result = ObraSignalVerificationAgent(Path(tmp), runner=runner).execute(payload)
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["error"], {"type": "INVALID_REQUEST"})
            self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
