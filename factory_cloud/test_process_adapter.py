import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from factory_cloud.adapters import ExecutionRequest
from factory_cloud.capabilities import Capability
from factory_cloud.process_adapter import ProcessAdapterConfig, ProcessAdapterConfigError, ProcessAgentAdapter


CANONICAL = "a" * 40
EXECUTION = "c" * 40
SENSITIVE = "private-process-output-must-not-persist"
VERIFY_CAPABILITIES = frozenset({Capability.READ_REPOSITORY, Capability.RUN_TESTS, Capability.UPDATE_BATON})
VERIFY_CAPABILITY_VALUES = tuple(sorted(item.value for item in VERIFY_CAPABILITIES))


class FakeRunner:
    def __init__(self, agent_result=None, agent_returncode=0, agent_stderr="", observed_head=CANONICAL):
        self.agent_result = agent_result or {"status": "DONE"}
        self.agent_returncode = agent_returncode
        self.agent_stderr = agent_stderr
        self.observed_head = observed_head
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if list(argv) == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, stdout=self.observed_head + "\n", stderr="")
        return subprocess.CompletedProcess(
            argv,
            self.agent_returncode,
            stdout=json.dumps(self.agent_result),
            stderr=self.agent_stderr,
        )


class MismatchRunner(FakeRunner):
    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if list(argv) == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, stdout="b" * 40 + "\n", stderr="")
        raise AssertionError("agent process must not run after local HEAD mismatch")


class ProcessAdapterTests(unittest.TestCase):
    def _request(self, **changes):
        payload = dict(
            app_id="obrasignal",
            mode="repository_safe_execution",
            task="safe repository task",
            source="MarcosTaz/Obrasignal",
            canonical_head=CANONICAL,
            resume_at="safe repository task",
            required_capabilities=VERIFY_CAPABILITY_VALUES,
        )
        payload.update(changes)
        return ExecutionRequest(**payload)

    def _config(self, root: Path, *command: str):
        return ProcessAdapterConfig(
            app_id="obrasignal",
            mode="repository_safe_execution",
            workspace=root,
            command=command or ("agent",),
            capabilities=VERIFY_CAPABILITIES,
        )

    def test_config_is_app_scoped_repository_safe_and_requires_explicit_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "adapter.json"
            config_path.write_text(json.dumps({
                "app_id": "k3-fatality",
                "mode": "repository_safe_execution",
                "workspace": str(Path(tmp).resolve()),
                "command": ["agent"],
                "capabilities": list(VERIFY_CAPABILITY_VALUES),
            }), encoding="utf-8")
            with self.assertRaises(ProcessAdapterConfigError):
                ProcessAdapterConfig.load(config_path, expected_app_id="obrasignal")

            config_path.write_text(json.dumps({
                "app_id": "obrasignal",
                "mode": "read_only_until_source_resolved",
                "workspace": str(Path(tmp).resolve()),
                "command": ["agent"],
                "capabilities": list(VERIFY_CAPABILITY_VALUES),
            }), encoding="utf-8")
            with self.assertRaises(ProcessAdapterConfigError):
                ProcessAdapterConfig.load(config_path, expected_app_id="obrasignal")

            config_path.write_text(json.dumps({
                "app_id": "obrasignal",
                "mode": "repository_safe_execution",
                "workspace": str(Path(tmp).resolve()),
                "command": ["agent"],
            }), encoding="utf-8")
            with self.assertRaises(ProcessAdapterConfigError):
                ProcessAdapterConfig.load(config_path, expected_app_id="obrasignal")

    def test_local_head_mismatch_fails_closed_before_agent_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = MismatchRunner()
            result = ProcessAgentAdapter(self._config(Path(tmp)), runner=runner).execute(self._request())
            self.assertEqual(result.status, "WAIT")
            self.assertIn("local_workspace_head_mismatch", result.blockers)
            self.assertEqual(len(runner.calls), 1)

    def test_missing_required_capability_blocks_before_workspace_or_agent_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProcessAdapterConfig(
                app_id="obrasignal",
                mode="repository_safe_execution",
                workspace=Path(tmp),
                command=("agent",),
                capabilities=frozenset({Capability.READ_REPOSITORY}),
            )
            runner = FakeRunner()
            result = ProcessAgentAdapter(config, runner=runner).execute(self._request())
            self.assertEqual(result.status, "BLOCKED")
            self.assertEqual(result.evidence["task_state"], "AUTHORITY_REQUIRED")
            self.assertIn("adapter_capability_required", result.blockers)
            self.assertEqual(runner.calls, [])

    def test_execution_head_overrides_canonical_for_local_gate_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = {
                "status": "DONE",
                "evidence": {"commit_sha": EXECUTION, "verified_head": EXECUTION, "test_state": "SUCCESS"},
                "last_green": EXECUTION,
            }
            runner = FakeRunner(agent_result=raw, observed_head=EXECUTION)
            result = ProcessAgentAdapter(self._config(Path(tmp)), runner=runner).execute(self._request(
                execution_branch="integration/current-spine",
                execution_head=EXECUTION,
            ))
            self.assertEqual(result.status, "DONE")
            payload = json.loads(runner.calls[1][1]["input"])
            self.assertEqual(payload["canonical_head"], CANONICAL)
            self.assertEqual(payload["execution_head"], EXECUTION)
            self.assertEqual(payload["execution_branch"], "integration/current-spine")
            self.assertEqual(tuple(payload["required_capabilities"]), VERIFY_CAPABILITY_VALUES)
            self.assertEqual(result.evidence["local_head"], EXECUTION)

    def test_success_contract_persists_only_bounded_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = {
                "status": "DONE",
                "evidence": {
                    "commit_sha": CANONICAL,
                    "verified_head": CANONICAL,
                    "test_state": "SUCCESS",
                    "evidence_codes": ["pytest:green"],
                    "raw_log": SENSITIVE,
                },
                "next_active": "next safe task",
                "next_items": ["next safe task"],
                "wait_items": ["production deploy"],
                "blockers": [],
                "resume_at": "next safe task",
                "last_green": CANONICAL,
            }
            runner = FakeRunner(agent_result=raw, agent_stderr=SENSITIVE)
            result = ProcessAgentAdapter(self._config(Path(tmp), "agent", "execute"), runner=runner).execute(self._request())
            self.assertEqual(result.status, "DONE")
            self.assertEqual(result.next_active, "next safe task")
            self.assertEqual(result.evidence["test_state"], "SUCCESS")
            self.assertNotIn("raw_log", result.evidence)
            self.assertNotIn(SENSITIVE, str(result))
            self.assertEqual(len(runner.calls), 2)
            payload = json.loads(runner.calls[1][1]["input"])
            self.assertEqual(payload["canonical_head"], CANONICAL)
            self.assertIsNone(payload["execution_head"])

    def test_nonzero_exit_never_persists_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = FakeRunner(agent_returncode=7, agent_stderr=SENSITIVE)
            result = ProcessAgentAdapter(self._config(Path(tmp)), runner=runner).execute(self._request())
            self.assertEqual(result.status, "ERROR")
            self.assertEqual(result.error, {"type": "APP_AGENT_NONZERO_EXIT"})
            self.assertEqual(result.evidence["exit_code"], 7)
            self.assertNotIn(SENSITIVE, str(result))

    def test_invalid_agent_json_fails_closed_without_raw_output(self):
        class InvalidRunner(FakeRunner):
            def __call__(self, argv, **kwargs):
                self.calls.append((list(argv), kwargs))
                if list(argv) == ["git", "rev-parse", "HEAD"]:
                    return subprocess.CompletedProcess(argv, 0, stdout=CANONICAL + "\n", stderr="")
                return subprocess.CompletedProcess(argv, 0, stdout=SENSITIVE, stderr=SENSITIVE)

        with tempfile.TemporaryDirectory() as tmp:
            runner = InvalidRunner()
            result = ProcessAgentAdapter(self._config(Path(tmp)), runner=runner).execute(self._request())
            self.assertEqual(result.status, "ERROR")
            self.assertEqual(result.error, {"type": "APP_AGENT_INVALID_RESULT"})
            self.assertNotIn(SENSITIVE, str(result))


if __name__ == "__main__":
    unittest.main()
