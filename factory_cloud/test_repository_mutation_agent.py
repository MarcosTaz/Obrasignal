import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factory_cloud.capabilities import Capability
from factory_cloud.repository_mutation_agent import (
    GitHubPullRequestClient,
    RepositoryAgentConfigError,
    RepositoryMutationAgent,
    RepositoryMutationConfig,
)


MUTATION_CAPS = frozenset({
    Capability.READ_REPOSITORY,
    Capability.CREATE_BRANCH,
    Capability.WRITE_FILES,
    Capability.RUN_TESTS,
    Capability.UPDATE_BATON,
})
MUTATION_VALUES = sorted(item.value for item in MUTATION_CAPS)


def run_git(root: Path, *args: str):
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def make_repo(root: Path):
    repo = root / "repo"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "canary@example.invalid")
    run_git(repo, "config", "user.name", "Factory Canary")
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    run_git(repo, "add", "app.py")
    run_git(repo, "commit", "-m", "seed")
    run_git(repo, "branch", "-M", "main")
    return repo, run_git(repo, "rev-parse", "HEAD").stdout.strip()


def write_catalog(path: Path, task: dict):
    path.write_text(json.dumps({"tasks": {"canary:change": task}}), encoding="utf-8")


def config_for(repo: Path, catalog: Path, *, test_command, capabilities=MUTATION_CAPS):
    return RepositoryMutationConfig(
        app_id="canary-a",
        repository="local/canary-a",
        workspace=repo,
        canonical_branch="main",
        allowed_branch_prefix="factory-cloud/canary-a/",
        task_catalog=catalog,
        test_commands={"acceptance": tuple(test_command)},
        capabilities=capabilities,
        timeout_seconds=30,
    )


def request(head: str, *, capabilities=MUTATION_VALUES):
    return {
        "app_id": "canary-a",
        "mode": "repository_safe_execution",
        "task": "canary:change",
        "source": "local/canary-a",
        "canonical_head": head,
        "execution_branch": "main",
        "execution_head": head,
        "required_capabilities": list(capabilities),
        "resume_at": "canary:change",
    }


class RepositoryMutationAgentTests(unittest.TestCase):
    def test_green_task_creates_only_authorized_branch_commit_and_execution_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, head = make_repo(root)
            catalog = root / "tasks.json"
            write_catalog(catalog, {
                "work_branch": "factory-cloud/canary-a/change",
                "writes": [{"path": "app.py", "content": "VALUE = 2\n"}],
                "tests": ["acceptance"],
                "commit_message": "canary: change value",
                "publish": False,
            })
            command = [sys.executable, "-c", "from pathlib import Path; assert Path('app.py').read_text() == 'VALUE = 2\\n'"]
            result = RepositoryMutationAgent(config_for(repo, catalog, test_command=command)).execute(request(head))

            self.assertEqual(result["status"], "DONE")
            self.assertEqual(result["execution_branch"], "factory-cloud/canary-a/change")
            self.assertNotEqual(result["execution_head"], head)
            self.assertEqual(result["execution_head"], run_git(repo, "rev-parse", "HEAD").stdout.strip())
            self.assertEqual(run_git(repo, "branch", "--show-current").stdout.strip(), "factory-cloud/canary-a/change")
            self.assertEqual((repo / "app.py").read_text(encoding="utf-8"), "VALUE = 2\n")
            self.assertEqual(run_git(repo, "status", "--porcelain").stdout, "")
            self.assertEqual(result["evidence"]["test_state"], "SUCCESS")

    def test_failing_test_rolls_back_files_head_and_local_work_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, head = make_repo(root)
            catalog = root / "tasks.json"
            write_catalog(catalog, {
                "work_branch": "factory-cloud/canary-a/failing",
                "writes": [{"path": "app.py", "content": "VALUE = 999\n"}],
                "tests": ["acceptance"],
                "commit_message": "must never commit",
                "publish": False,
            })
            result = RepositoryMutationAgent(config_for(repo, catalog, test_command=[sys.executable, "-c", "raise SystemExit(9)"])).execute(request(head))

            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["evidence"]["task_state"], "TEST_FAILED")
            self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)
            self.assertEqual((repo / "app.py").read_text(encoding="utf-8"), "VALUE = 1\n")
            self.assertEqual(run_git(repo, "status", "--porcelain").stdout, "")
            branches = run_git(repo, "branch", "--format=%(refname:short)").stdout.splitlines()
            self.assertNotIn("factory-cloud/canary-a/failing", branches)

    def test_unexpected_test_side_effect_is_error_and_rolled_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, head = make_repo(root)
            catalog = root / "tasks.json"
            write_catalog(catalog, {
                "work_branch": "factory-cloud/canary-a/side-effect",
                "writes": [{"path": "app.py", "content": "VALUE = 2\n"}],
                "tests": ["acceptance"],
                "commit_message": "must roll back",
                "publish": False,
            })
            command = [sys.executable, "-c", "from pathlib import Path; Path('unexpected.txt').write_text('x')"]
            result = RepositoryMutationAgent(config_for(repo, catalog, test_command=command)).execute(request(head))

            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["evidence"]["task_state"], "UNEXPECTED_REPOSITORY_SIDE_EFFECT")
            self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)
            self.assertFalse((repo / "unexpected.txt").exists())
            self.assertEqual(run_git(repo, "status", "--porcelain").stdout, "")

    def test_capability_mismatch_and_dangerous_branch_fail_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, head = make_repo(root)
            catalog = root / "tasks.json"
            write_catalog(catalog, {
                "work_branch": "main",
                "writes": [{"path": "app.py", "content": "VALUE = 2\n"}],
                "tests": ["acceptance"],
                "commit_message": "unsafe",
                "publish": False,
            })
            command = [sys.executable, "-c", "pass"]
            agent = RepositoryMutationAgent(config_for(repo, catalog, test_command=command))
            result = agent.execute(request(head))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)

            write_catalog(catalog, {
                "work_branch": "factory-cloud/canary-a/caps",
                "writes": [{"path": "app.py", "content": "VALUE = 2\n"}],
                "tests": ["acceptance"],
                "commit_message": "caps",
                "publish": False,
            })
            result = agent.execute(request(head, capabilities=["READ_REPOSITORY"]))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)

    def test_path_escape_and_git_metadata_write_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, head = make_repo(root)
            catalog = root / "tasks.json"
            for unsafe in ("../escape.txt", ".git/config"):
                write_catalog(catalog, {
                    "work_branch": "factory-cloud/canary-a/path",
                    "writes": [{"path": unsafe, "content": "unsafe"}],
                    "tests": ["acceptance"],
                    "commit_message": "unsafe",
                    "publish": False,
                })
                result = RepositoryMutationAgent(config_for(repo, catalog, test_command=[sys.executable, "-c", "pass"])).execute(request(head))
                self.assertEqual(result["status"], "ERROR")
                self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)
                self.assertEqual(run_git(repo, "status", "--porcelain").stdout, "")

    def test_high_risk_capability_cannot_enter_repository_agent_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, _ = make_repo(root)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "app_id": "canary-a",
                "repository": "local/canary-a",
                "workspace": str(repo),
                "canonical_branch": "main",
                "allowed_branch_prefix": "factory-cloud/canary-a/",
                "task_catalog": str(root / "tasks.json"),
                "test_commands": {"acceptance": [sys.executable, "-c", "pass"]},
                "capabilities": MUTATION_VALUES + ["MERGE_MAIN"],
            }), encoding="utf-8")
            with self.assertRaises(RepositoryAgentConfigError):
                RepositoryMutationConfig.load(config_path)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RecordingOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []
    def __call__(self, request, timeout):
        self.requests.append(request)
        return FakeResponse(self.payloads.pop(0))


class GitHubPullRequestClientTests(unittest.TestCase):
    def test_client_creates_pr_but_has_no_merge_operation(self):
        opener = RecordingOpener([[], {"number": 42, "html_url": "https://example.invalid/pr/42"}])
        client = GitHubPullRequestClient("owner/repo", "token-value", opener=opener)
        number, _ = client.upsert(head_branch="factory-cloud/canary-a/change", base_branch="integration", title="Canary", body="safe")
        self.assertEqual(number, "42")
        self.assertEqual([request.get_method() for request in opener.requests], ["GET", "POST"])
        self.assertIn("/pulls", opener.requests[1].full_url)
        self.assertFalse(hasattr(client, "merge"))
        self.assertNotIn("token-value", str([request.full_url for request in opener.requests]))

    def test_client_updates_existing_pr_instead_of_creating_duplicate(self):
        opener = RecordingOpener([[{"number": 7}], {"number": 7, "html_url": "https://example.invalid/pr/7"}])
        client = GitHubPullRequestClient("owner/repo", "token-value", opener=opener)
        number, _ = client.upsert(head_branch="factory-cloud/canary-a/change", base_branch="integration", title="Canary", body="updated")
        self.assertEqual(number, "7")
        self.assertEqual([request.get_method() for request in opener.requests], ["GET", "PATCH"])


if __name__ == "__main__":
    unittest.main()
