from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from .models import Evidence, RepositoryState, TruthState


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class GitHubAdapter:
    """Read-only repository/deployment adapter. Public repos work without a token; private repos fail closed to UNKNOWN."""

    def __init__(self, token: str | None = None, timeout: int = 8):
        self.token = token or os.getenv("FCC_GITHUB_TOKEN")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _ci_state(self, full_name: str, commit: str, headers: dict[str, str]) -> tuple[TruthState, str]:
        """Conservatively combine checks and commit statuses. Absence of evidence stays UNKNOWN."""
        try:
            checks_response = requests.get(f"https://api.github.com/repos/{full_name}/commits/{commit}/check-runs", headers=headers, timeout=self.timeout)
            statuses_response = requests.get(f"https://api.github.com/repos/{full_name}/commits/{commit}/status", headers=headers, timeout=self.timeout)
            checks = []
            status_state = None
            if checks_response.ok:
                checks = checks_response.json().get("check_runs", [])
            if statuses_response.ok:
                status_state = statuses_response.json().get("state")
            failed = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
            running = {"queued", "in_progress", "requested", "waiting", "pending"}
            check_conclusions = {item.get("conclusion") for item in checks if item.get("status") == "completed"}
            check_statuses = {item.get("status") for item in checks}
            if check_conclusions & failed or status_state in ("failure", "error"):
                return TruthState.DEGRADED, "CI/check evidence contains a failing state."
            if check_statuses & running or status_state == "pending":
                return TruthState.UNKNOWN, "CI/check evidence is still running or pending."
            if checks and all(item.get("status") == "completed" and item.get("conclusion") in ("success", "neutral", "skipped") for item in checks):
                if status_state in (None, "success", "expected"):
                    return TruthState.GREEN, f"{len(checks)} completed GitHub check run(s) contain no failure."
            if status_state == "success" and not checks:
                return TruthState.GREEN, "GitHub combined commit status is success."
            return TruthState.UNKNOWN, "No complete CI proof is available for this commit."
        except requests.RequestException as exc:
            return TruthState.UNKNOWN, f"CI evidence could not be refreshed: {type(exc).__name__}."

    def refresh_repo(self, full_name: str) -> RepositoryState:
        evidence = Evidence(source=f"github:{full_name}", observed_at=utcnow(), freshness_seconds=3600, kind="live_adapter", url=f"https://github.com/{full_name}")
        headers = self._headers()
        try:
            repo = requests.get(f"https://api.github.com/repos/{full_name}", headers=headers, timeout=self.timeout)
            if repo.status_code in (401, 403, 404) and not self.token:
                evidence.detail = "Repository is not publicly accessible. Configure FCC_GITHUB_TOKEN for private repository truth; state remains UNKNOWN."
                return RepositoryState(full_name=full_name, ci=TruthState.UNKNOWN, evidence=evidence)
            repo.raise_for_status()
            data = repo.json(); branch = data.get("default_branch"); commit = None; ci = TruthState.UNKNOWN; ci_detail = "No commit available for CI proof."
            if branch:
                ref = requests.get(f"https://api.github.com/repos/{full_name}/commits/{branch}", headers=headers, timeout=self.timeout)
                ref.raise_for_status(); commit = ref.json().get("sha")
            if commit:
                ci, ci_detail = self._ci_state(full_name, commit, headers)
            evidence.detail = f"Live GitHub repository snapshot. {ci_detail}"
            return RepositoryState(full_name, branch, commit, ci, evidence)
        except requests.RequestException as exc:
            evidence.detail = f"GitHub adapter transport failure: {type(exc).__name__}"
            return RepositoryState(full_name=full_name, ci=TruthState.DEGRADED, evidence=evidence)

    def refresh_deployment(self, full_name: str) -> tuple[TruthState, Evidence, str | None]:
        """Read latest GitHub deployment/status without equating repository green with production green."""
        evidence = Evidence(source=f"github-deployments:{full_name}", observed_at=utcnow(), freshness_seconds=600, kind="live_adapter", url=f"https://github.com/{full_name}/deployments")
        headers = self._headers()
        try:
            response = requests.get(f"https://api.github.com/repos/{full_name}/deployments?per_page=1", headers=headers, timeout=self.timeout)
            if response.status_code in (401, 403, 404) and not self.token:
                evidence.detail = "Deployment source is not publicly accessible; deployment state remains UNKNOWN."
                return TruthState.UNKNOWN, evidence, None
            response.raise_for_status()
            deployments = response.json()
            if not deployments:
                evidence.detail = "No GitHub deployment exists; absence of a deployment is not deployment health."
                return TruthState.UNKNOWN, evidence, None
            deployment = deployments[0]
            deployment_id = deployment.get("id")
            environment = deployment.get("environment") or "unknown environment"
            deploy_sha = deployment.get("sha") or "unknown sha"
            if not deployment_id:
                evidence.detail = f"Latest deployment for {environment} has no resolvable deployment id."
                return TruthState.UNKNOWN, evidence, None
            statuses = requests.get(f"https://api.github.com/repos/{full_name}/deployments/{deployment_id}/statuses?per_page=1", headers=headers, timeout=self.timeout)
            statuses.raise_for_status()
            status_items = statuses.json()
            if not status_items:
                evidence.detail = f"Deployment {deployment_id} ({environment}, {deploy_sha}) has no status evidence."
                return TruthState.UNKNOWN, evidence, None
            status = status_items[0]
            state = status.get("state")
            environment_url = status.get("environment_url") or deployment.get("environment_url")
            target_url = status.get("target_url")
            if environment_url:
                evidence.url = environment_url
            elif target_url:
                evidence.url = target_url
            evidence.detail = f"GitHub deployment {deployment_id}; environment={environment}; sha={deploy_sha}; state={state or 'UNKNOWN'}."
            if state == "success":
                return TruthState.GREEN, evidence, environment_url
            if state in ("failure", "error"):
                return TruthState.DEGRADED, evidence, environment_url
            return TruthState.UNKNOWN, evidence, environment_url
        except requests.RequestException as exc:
            evidence.detail = f"Deployment adapter transport failure: {type(exc).__name__}"
            return TruthState.DEGRADED, evidence, None


class HealthAdapter:
    def refresh(self, url: str) -> tuple[TruthState, Evidence]:
        evidence = Evidence(source=url, observed_at=utcnow(), freshness_seconds=300, kind="live_adapter")
        try:
            response = requests.get(url, timeout=6)
            if 200 <= response.status_code < 300:
                evidence.detail = f"HTTP {response.status_code}; transport green only, not business correctness."
                return TruthState.GREEN, evidence
            evidence.detail = f"HTTP {response.status_code}"
            return TruthState.DEGRADED, evidence
        except requests.RequestException as exc:
            evidence.detail = f"Health adapter failed: {type(exc).__name__}"
            return TruthState.DEGRADED, evidence
