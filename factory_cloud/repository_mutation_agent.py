from __future__ import annotations

"""Capability-scoped repository mutation agent for isolated Factory Cloud workers.

Task details live in an app-owned catalog outside the shared queue. The control plane
carries only a task id, exact source heads and capabilities. This agent never merges,
deploys, reads customer data, activates billing, rotates secrets or contacts customers.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if __package__ in {None, ""}:
    control_root = str(Path(__file__).resolve().parents[1])
    if control_root not in sys.path:
        sys.path.insert(0, control_root)

from factory_cloud.capabilities import Capability, CapabilityContractError, parse_capabilities, require_capabilities

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
MAX_WRITE_BYTES = 262_144
MAX_WRITES = 50
MAX_TESTS = 20
MAX_COMMAND_ARGS = 64
MAX_TEXT = 4096


class RepositoryAgentConfigError(ValueError):
    pass


class RepositoryMutationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class GitHubPublishError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _text(value: Any, field: str, *, required: bool = True, limit: int = MAX_TEXT) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise RepositoryAgentConfigError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise RepositoryAgentConfigError(f"{field} is required")
    if len(value) > limit:
        raise RepositoryAgentConfigError(f"{field} exceeds limit")
    return value


def _argv(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > MAX_COMMAND_ARGS:
        raise RepositoryAgentConfigError(f"{field} must be a bounded non-empty argv list")
    return tuple(_text(item, field, limit=512) for item in value)


@dataclass(frozen=True)
class MutationTask:
    task_id: str
    work_branch: str
    writes: tuple[tuple[str, str], ...]
    test_ids: tuple[str, ...]
    commit_message: str
    publish: bool
    pr_title: str | None = None
    pr_body: str | None = None
    pr_base: str | None = None

    @property
    def required_capabilities(self) -> frozenset[Capability]:
        required = {
            Capability.READ_REPOSITORY,
            Capability.CREATE_BRANCH,
            Capability.WRITE_FILES,
            Capability.RUN_TESTS,
            Capability.UPDATE_BATON,
        }
        if self.publish:
            required.add(Capability.CREATE_PR)
        return frozenset(required)


@dataclass(frozen=True)
class RepositoryMutationConfig:
    app_id: str
    repository: str
    workspace: Path
    canonical_branch: str
    allowed_branch_prefix: str
    task_catalog: Path
    test_commands: Mapping[str, tuple[str, ...]]
    capabilities: frozenset[Capability]
    push_remote: str | None = None
    allowed_pr_bases: tuple[str, ...] = ()
    github_token_env: str | None = None
    github_api_base: str = "https://api.github.com"
    timeout_seconds: float = 1200.0

    @classmethod
    def load(cls, path: Path, *, expected_app_id: str | None = None) -> "RepositoryMutationConfig":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryAgentConfigError("repository agent config unreadable or invalid") from exc
        if not isinstance(payload, dict):
            raise RepositoryAgentConfigError("repository agent config must be an object")
        app_id = _text(payload.get("app_id"), "app_id", limit=128)
        if expected_app_id and app_id != expected_app_id:
            raise RepositoryAgentConfigError("repository agent app_id mismatch")
        repository = _text(payload.get("repository"), "repository", limit=256)
        if repository.count("/") != 1:
            raise RepositoryAgentConfigError("repository must be owner/name")
        workspace = Path(_text(payload.get("workspace"), "workspace", limit=1024))
        task_catalog = Path(_text(payload.get("task_catalog"), "task_catalog", limit=1024))
        if not workspace.is_absolute() or not task_catalog.is_absolute():
            raise RepositoryAgentConfigError("workspace and task_catalog must be absolute paths")
        canonical_branch = _text(payload.get("canonical_branch"), "canonical_branch", limit=200)
        prefix = _text(payload.get("allowed_branch_prefix"), "allowed_branch_prefix", limit=120)
        if not BRANCH_RE.fullmatch(canonical_branch) or not BRANCH_RE.fullmatch(prefix.rstrip("/")):
            raise RepositoryAgentConfigError("invalid branch policy")
        if not prefix.endswith("/"):
            raise RepositoryAgentConfigError("allowed_branch_prefix must end with /")
        try:
            capabilities = parse_capabilities(payload.get("capabilities"), require_explicit=True)
        except CapabilityContractError as exc:
            raise RepositoryAgentConfigError(str(exc)) from exc
        commands_raw = payload.get("test_commands")
        if not isinstance(commands_raw, dict) or not commands_raw:
            raise RepositoryAgentConfigError("test_commands must be a non-empty object")
        commands = {str(key): _argv(value, f"test_commands.{key}") for key, value in commands_raw.items()}
        remote = _text(payload.get("push_remote"), "push_remote", required=False, limit=128) or None
        bases_raw = payload.get("allowed_pr_bases") or []
        if not isinstance(bases_raw, list):
            raise RepositoryAgentConfigError("allowed_pr_bases must be a list")
        bases = tuple(_text(item, "allowed_pr_bases", limit=200) for item in bases_raw)
        token_env = _text(payload.get("github_token_env"), "github_token_env", required=False, limit=128) or None
        api_base = _text(payload.get("github_api_base") or "https://api.github.com", "github_api_base", limit=512).rstrip("/")
        timeout = payload.get("timeout_seconds", 1200.0)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0 or timeout > 21600:
            raise RepositoryAgentConfigError("timeout_seconds must be > 0 and <= 21600")
        return cls(
            app_id=app_id, repository=repository, workspace=workspace, canonical_branch=canonical_branch,
            allowed_branch_prefix=prefix, task_catalog=task_catalog, test_commands=commands,
            capabilities=capabilities, push_remote=remote, allowed_pr_bases=bases,
            github_token_env=token_env, github_api_base=api_base, timeout_seconds=float(timeout),
        )

    def load_task(self, task_id: str) -> MutationTask:
        try:
            payload = json.loads(self.task_catalog.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryMutationError("task_catalog_unavailable") from exc
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        raw = tasks.get(task_id) if isinstance(tasks, dict) else None
        if not isinstance(raw, dict):
            raise RepositoryMutationError("task_not_in_isolated_catalog")
        branch = _text(raw.get("work_branch"), "work_branch", limit=200)
        if not BRANCH_RE.fullmatch(branch) or not branch.startswith(self.allowed_branch_prefix):
            raise RepositoryMutationError("work_branch_outside_authorized_prefix")
        if branch == self.canonical_branch:
            raise RepositoryMutationError("canonical_branch_mutation_rejected")
        writes_raw = raw.get("writes")
        if not isinstance(writes_raw, list) or not writes_raw or len(writes_raw) > MAX_WRITES:
            raise RepositoryMutationError("writes_contract_invalid")
        writes: list[tuple[str, str]] = []
        seen: set[str] = set()
        for item in writes_raw:
            if not isinstance(item, dict):
                raise RepositoryMutationError("writes_contract_invalid")
            rel = _text(item.get("path"), "write.path", limit=512)
            content = item.get("content")
            if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_WRITE_BYTES:
                raise RepositoryMutationError("write_content_invalid")
            if rel in seen:
                raise RepositoryMutationError("duplicate_write_path")
            seen.add(rel)
            writes.append((rel, content))
        tests_raw = raw.get("tests")
        if not isinstance(tests_raw, list) or not tests_raw or len(tests_raw) > MAX_TESTS:
            raise RepositoryMutationError("tests_contract_invalid")
        test_ids = tuple(_text(item, "test_id", limit=128) for item in tests_raw)
        if any(test_id not in self.test_commands for test_id in test_ids):
            raise RepositoryMutationError("test_command_not_allowlisted")
        message = _text(raw.get("commit_message"), "commit_message", limit=512)
        publish = raw.get("publish") is True
        pr = raw.get("pr") or {}
        if publish:
            if not self.push_remote or not self.github_token_env:
                raise RepositoryMutationError("publish_configuration_incomplete")
            if not isinstance(pr, dict):
                raise RepositoryMutationError("pr_contract_invalid")
            title = _text(pr.get("title"), "pr.title", limit=512)
            body = _text(pr.get("body"), "pr.body", required=False, limit=16_384)
            base = _text(pr.get("base"), "pr.base", limit=200)
            if base not in self.allowed_pr_bases:
                raise RepositoryMutationError("pr_base_not_allowlisted")
        else:
            title = body = base = None
        return MutationTask(task_id, branch, tuple(writes), test_ids, message, publish, title, body, base)


class GitHubPullRequestClient:
    """PR-only GitHub API client. No merge endpoint exists in this class."""

    def __init__(self, repository: str, token: str, api_base: str = "https://api.github.com", opener: Callable[..., Any] | None = None):
        if not token:
            raise GitHubPublishError("github_token_unavailable")
        self.repository = repository
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.opener = opener or urllib.request.urlopen

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.api_base}{path}", data=data, method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Factory-Cloud-Repository-Agent",
            },
        )
        try:
            with self.opener(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise GitHubPublishError("github_pr_api_unavailable") from exc

    def upsert(self, *, head_branch: str, base_branch: str, title: str, body: str) -> tuple[str, str]:
        owner = self.repository.split("/", 1)[0]
        query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{head_branch}", "base": base_branch})
        existing = self._request("GET", f"/repos/{self.repository}/pulls?{query}")
        if not isinstance(existing, list):
            raise GitHubPublishError("github_pr_lookup_invalid")
        if existing:
            number = existing[0].get("number")
            if not isinstance(number, int):
                raise GitHubPublishError("github_pr_lookup_invalid")
            result = self._request("PATCH", f"/repos/{self.repository}/pulls/{number}", {"title": title, "body": body, "base": base_branch})
        else:
            result = self._request("POST", f"/repos/{self.repository}/pulls", {"title": title, "body": body, "head": head_branch, "base": base_branch})
        if not isinstance(result, dict) or not isinstance(result.get("number"), int):
            raise GitHubPublishError("github_pr_result_invalid")
        return str(result["number"]), str(result.get("html_url") or "")


class RepositoryMutationAgent:
    def __init__(self, config: RepositoryMutationConfig, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run, opener: Callable[..., Any] | None = None, environ: Mapping[str, str] | None = None):
        self.config = config
        self.runner = runner
        self.opener = opener
        self.environ = dict(os.environ if environ is None else environ)
        self.workspace = config.workspace.resolve()

    def _run(self, argv: Sequence[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        return self.runner(list(argv), cwd=self.workspace, text=True, capture_output=True, timeout=timeout or self.config.timeout_seconds, check=False, env=dict(self.environ))

    def _git(self, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
        return self._run(("git", *args), timeout=timeout)

    def _head(self) -> str | None:
        result = self._git("rev-parse", "HEAD")
        head = (result.stdout or "").strip()
        return head if result.returncode == 0 and SHA_RE.fullmatch(head) else None

    def _safe_path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or not path.parts or any(part in {"..", ".git"} for part in path.parts):
            raise RepositoryMutationError("write_path_rejected")
        candidate = (self.workspace / path).resolve(strict=False)
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise RepositoryMutationError("write_path_escape_rejected") from exc
        current = self.workspace
        for part in path.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise RepositoryMutationError("write_symlink_rejected")
        return candidate

    def _remove_untracked(self) -> bool:
        result = self._git("ls-files", "--others", "--exclude-standard", "-z")
        if result.returncode != 0:
            return False
        for relative in (result.stdout or "").split("\0"):
            if not relative:
                continue
            try:
                path = self._safe_path(relative)
            except RepositoryMutationError:
                return False
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
                parent = path.parent
                while parent != self.workspace:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
        return True

    def _rollback(self, expected_head: str, branch: str) -> bool:
        restored = self._git("restore", "--source", expected_head, "--staged", "--worktree", "--", ".")
        untracked_removed = self._remove_untracked()
        detached = self._git("checkout", "--detach", expected_head)
        deleted = self._git("branch", "-D", branch)
        clean = self._git("status", "--porcelain", "--untracked-files=all")
        return all(result.returncode == 0 for result in (restored, detached, deleted, clean)) and untracked_removed and not (clean.stdout or "").strip()

    @staticmethod
    def _blocked(task: str, code: str) -> dict[str, Any]:
        return {
            "status": "BLOCKED",
            "evidence": {"test_state": "NOT_RUN", "task_state": "AUTHORITY_REQUIRED", "evidence_codes": [code]},
            "next_active": task, "blockers": [code], "resume_at": task,
        }

    @staticmethod
    def _error(task: str, code: str, *, test_state: str = "FAILURE") -> dict[str, Any]:
        return {
            "status": "ERROR",
            "evidence": {"test_state": test_state, "task_state": code.upper(), "evidence_codes": [code]},
            "next_active": task, "blockers": [code], "resume_at": task, "error": {"type": code.upper()},
        }

    def _rollback_error(self, task: str, expected_head: str, branch: str, code: str, *, test_state: str = "FAILURE") -> dict[str, Any]:
        if not self._rollback(expected_head, branch):
            return self._error(task, "rollback_failed")
        return self._error(task, code, test_state=test_state)

    def execute(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return self._error("unknown", "invalid_request", test_state="NOT_RUN")
        task_id = str(payload.get("task") or "").strip()
        if not task_id:
            return self._error("unknown", "invalid_request", test_state="NOT_RUN")
        if payload.get("app_id") != self.config.app_id or payload.get("source") != self.config.repository or payload.get("mode") != "repository_safe_execution":
            return self._blocked(task_id, "repository_identity_mismatch")
        expected_head = str(payload.get("execution_head") or payload.get("canonical_head") or "").strip()
        if not SHA_RE.fullmatch(expected_head):
            return self._blocked(task_id, "source_mismatch")
        raw_caps = payload.get("required_capabilities")
        if not isinstance(raw_caps, list):
            return self._blocked(task_id, "capability_contract_missing")
        try:
            requested = parse_capabilities(raw_caps, require_explicit=True)
            task = self.config.load_task(task_id)
            require_capabilities(self.config.capabilities, requested)
        except (CapabilityContractError, RepositoryMutationError):
            return self._blocked(task_id, "authority_required")
        if requested != task.required_capabilities:
            return self._blocked(task_id, "capability_contract_mismatch")
        if not self.workspace.is_dir() or not (self.workspace / ".git").exists():
            return {"status": "WAIT", "evidence": {"test_state": "NOT_RUN", "task_state": "WORKSPACE_UNAVAILABLE", "evidence_codes": ["workspace_unavailable"]}, "next_active": task_id, "blockers": ["workspace_unavailable"], "resume_at": task_id}
        if self._head() != expected_head:
            return {"status": "WAIT", "evidence": {"test_state": "NOT_RUN", "task_state": "SOURCE_MISMATCH", "evidence_codes": ["source_mismatch"]}, "next_active": task_id, "blockers": ["source_mismatch"], "resume_at": task_id}
        clean = self._git("status", "--porcelain", "--untracked-files=all")
        if clean.returncode != 0 or (clean.stdout or "").strip():
            return self._blocked(task_id, "workspace_not_clean")
        branch_exists = self._git("show-ref", "--verify", "--quiet", f"refs/heads/{task.work_branch}")
        if branch_exists.returncode == 0:
            return self._blocked(task_id, "work_branch_already_exists")
        if self._git("checkout", "-b", task.work_branch, expected_head).returncode != 0:
            return self._error(task_id, "branch_creation_failed", test_state="NOT_RUN")

        write_paths: list[str] = []
        try:
            for relative, content in task.writes:
                target = self._safe_path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                write_paths.append(relative)

            for test_id in task.test_ids:
                result = self._run(self.config.test_commands[test_id])
                if result.returncode != 0:
                    return self._rollback_error(task_id, expected_head, task.work_branch, "test_failed")

            changed = self._git("diff", "--name-only", expected_head, "--", *write_paths)
            untracked = self._git("ls-files", "--others", "--exclude-standard")
            if changed.returncode != 0 or untracked.returncode != 0:
                return self._rollback_error(task_id, expected_head, task.work_branch, "repository_diff_unverifiable")
            observed_paths = {line.strip() for line in (changed.stdout or "").splitlines() if line.strip()}
            observed_paths.update(line.strip() for line in (untracked.stdout or "").splitlines() if line.strip())
            if not observed_paths or not observed_paths.issubset(set(write_paths)):
                return self._rollback_error(task_id, expected_head, task.work_branch, "unexpected_repository_side_effect")
            if self._git("add", "--", *write_paths).returncode != 0:
                return self._rollback_error(task_id, expected_head, task.work_branch, "git_stage_failed")
            if self._git("diff", "--cached", "--quiet").returncode == 0:
                if not self._rollback(expected_head, task.work_branch):
                    return self._error(task_id, "rollback_failed")
                return self._blocked(task_id, "no_repository_change")
            if self._git("commit", "-m", task.commit_message).returncode != 0:
                return self._rollback_error(task_id, expected_head, task.work_branch, "git_commit_failed")
            commit_sha = self._head()
            if not commit_sha:
                return self._rollback_error(task_id, expected_head, task.work_branch, "commit_head_unverifiable")

            evidence = {
                "commit_sha": commit_sha,
                "verified_head": commit_sha,
                "test_state": "SUCCESS",
                "task_state": "REPOSITORY_MUTATION_COMPLETE",
                "work_branch": task.work_branch,
                "evidence_codes": ["repository_mutation_green"],
            }
            if task.publish:
                if self._git("push", self.config.push_remote or "origin", f"HEAD:refs/heads/{task.work_branch}", timeout=180).returncode != 0:
                    return self._rollback_error(task_id, expected_head, task.work_branch, "repository_push_failed")
                token = self.environ.get(self.config.github_token_env or "", "")
                try:
                    pr_number, _ = GitHubPullRequestClient(self.config.repository, token, self.config.github_api_base, self.opener).upsert(
                        head_branch=task.work_branch,
                        base_branch=task.pr_base or self.config.canonical_branch,
                        title=task.pr_title or task.task_id,
                        body=task.pr_body or "",
                    )
                except GitHubPublishError as exc:
                    # The remote branch may already exist. Never fabricate DONE. Keep
                    # the local tested commit for auditable recovery and return ERROR.
                    return self._error(task_id, exc.code)
                evidence["pr_number"] = pr_number
                evidence["evidence_codes"].append("pull_request_upserted")

            return {
                "status": "DONE",
                "evidence": evidence,
                "blockers": [],
                "last_verified": commit_sha,
                "last_green": commit_sha,
                "execution_branch": task.work_branch,
                "execution_head": commit_sha,
            }
        except (OSError, RepositoryMutationError, subprocess.SubprocessError):
            try:
                rolled_back = self._rollback(expected_head, task.work_branch)
            except Exception:
                rolled_back = False
            return self._error(task_id, "repository_mutation_exception" if rolled_back else "rollback_failed")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--config":
        raise SystemExit("usage: repository_mutation_agent.py --config /absolute/config.json")
    try:
        config = RepositoryMutationConfig.load(Path(sys.argv[2]))
        payload = json.loads(sys.stdin.read())
    except (RepositoryAgentConfigError, json.JSONDecodeError):
        result = RepositoryMutationAgent._error("unknown", "invalid_request", test_state="NOT_RUN")
    else:
        result = RepositoryMutationAgent(config).execute(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
