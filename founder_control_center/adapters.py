from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests

from .models import Evidence, RepositoryState, TruthState
from .security import UnsafeDestination, normalize_github_repository, secret_is_usable, validate_public_http_url, validated_redirect_target


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_object(response, label: str) -> dict:
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"{label} response must be an object")
    return payload


def _json_list(response, label: str) -> list:
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"{label} response must be a list")
    return payload


class GitHubAdapter:
    """Read-only repository/deployment adapter. Public repos work without a token; inaccessible source truth fails closed to UNKNOWN."""

    def __init__(self, token: str | None = None, timeout: int = 8):
        configured = os.getenv("FCC_GITHUB_TOKEN") if token is None else token
        self.token = configured if secret_is_usable(configured, 16) else None
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _ci_state(self, full_name: str, commit: str, headers: dict[str, str]) -> tuple[TruthState, str]:
        """Conservatively combine checks and commit statuses. Absence or partial source failure never proves GREEN."""
        try:
            checks_response = requests.get(f"https://api.github.com/repos/{full_name}/commits/{commit}/check-runs", headers=headers, timeout=self.timeout)
            statuses_response = requests.get(f"https://api.github.com/repos/{full_name}/commits/{commit}/status", headers=headers, timeout=self.timeout)

            checks: list[dict] = []
            status_state = None
            status_count = 0
            malformed = False

            if checks_response.ok:
                try:
                    checks_payload = _json_object(checks_response, "GitHub check-runs")
                    raw_checks = checks_payload.get("check_runs", [])
                    if not isinstance(raw_checks, list) or any(not isinstance(item, dict) for item in raw_checks):
                        raise ValueError("GitHub check_runs must be a list of objects")
                    checks = raw_checks
                except (ValueError, TypeError, AttributeError):
                    malformed = True

            if statuses_response.ok:
                try:
                    statuses_payload = _json_object(statuses_response, "GitHub combined status")
                    status_state = statuses_payload.get("state")
                    total_count = statuses_payload.get("total_count")
                    if total_count is None:
                        raw_statuses = statuses_payload.get("statuses")
                        if not isinstance(raw_statuses, list):
                            raise ValueError("GitHub combined status must include total_count or a statuses list")
                        if any(not isinstance(item, dict) for item in raw_statuses):
                            raise ValueError("GitHub statuses must be a list of objects")
                        status_count = len(raw_statuses)
                    else:
                        if isinstance(total_count, bool) or not isinstance(total_count, int):
                            raise ValueError("GitHub combined status total_count must be an integer")
                        status_count = total_count
                        if status_count < 0:
                            raise ValueError("GitHub combined status total_count cannot be negative")
                except (ValueError, TypeError, AttributeError):
                    malformed = True

            failed = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
            running = {"queued", "in_progress", "requested", "waiting", "pending"}
            check_conclusions = {item.get("conclusion") for item in checks if item.get("status") == "completed"}
            check_statuses = {item.get("status") for item in checks}
            status_failed = status_count > 0 and status_state in ("failure", "error")
            status_pending = status_count > 0 and status_state in ("pending", "expected")

            if check_conclusions & failed or status_failed:
                return TruthState.DEGRADED, "CI/check evidence contains a failing state."

            if not checks_response.ok or not statuses_response.ok:
                return TruthState.UNKNOWN, "One or more GitHub CI evidence channels are inaccessible; success is not proven."
            if malformed:
                return TruthState.UNKNOWN, "GitHub CI evidence shape is malformed; success is not proven."
            if check_statuses & running or status_pending:
                return TruthState.UNKNOWN, "CI/check evidence is still running, pending or expected."
            if any(item.get("conclusion") in ("neutral", "skipped") for item in checks):
                return TruthState.UNKNOWN, "CI/check evidence contains neutral or skipped checks; success is not proven."

            if checks:
                all_checks_success = all(item.get("status") == "completed" and item.get("conclusion") == "success" for item in checks)
                statuses_compatible = status_count == 0 or status_state == "success"
                if all_checks_success and statuses_compatible:
                    suffix = "no separate commit statuses are present" if status_count == 0 else "combined commit status is success"
                    return TruthState.GREEN, f"{len(checks)} completed GitHub check run(s) are explicitly successful and {suffix}."

            if not checks and status_count > 0 and status_state == "success":
                return TruthState.GREEN, "GitHub combined commit status is explicitly successful and no check runs are present."

            return TruthState.UNKNOWN, "No complete CI proof is available for this commit."
        except requests.RequestException as exc:
            return TruthState.UNKNOWN, f"CI evidence could not be refreshed: {type(exc).__name__}."

    def refresh_repo(self, full_name: str) -> RepositoryState:
        try:
            full_name = normalize_github_repository(full_name)
        except ValueError as exc:
            evidence = Evidence(source="github:invalid-repository", observed_at=utcnow(), freshness_seconds=3600, kind="live_adapter", detail=f"Repository identifier rejected before GitHub access: {exc}")
            return RepositoryState(full_name=str(full_name)[:200], ci=TruthState.UNKNOWN, evidence=evidence)
        evidence = Evidence(source=f"github:{full_name}", observed_at=utcnow(), freshness_seconds=3600, kind="live_adapter", url=f"https://github.com/{full_name}")
        headers = self._headers()
        try:
            repo = requests.get(f"https://api.github.com/repos/{full_name}", headers=headers, timeout=self.timeout)
            if repo.status_code in (401, 403, 404):
                if self.token:
                    evidence.detail = "GitHub repository source is inaccessible with the configured credential; CI truth remains UNKNOWN."
                else:
                    evidence.detail = "Repository is not publicly accessible. Configure FCC_GITHUB_TOKEN for private repository truth; CI state remains UNKNOWN."
                return RepositoryState(full_name=full_name, ci=TruthState.UNKNOWN, evidence=evidence)
            repo.raise_for_status()
            data = _json_object(repo, "GitHub repository")
            branch = data.get("default_branch")
            if branch is not None and not isinstance(branch, str):
                raise ValueError("GitHub default_branch must be a string")
            commit = None
            ci = TruthState.UNKNOWN
            ci_detail = "No commit available for CI proof."
            if branch:
                ref = requests.get(f"https://api.github.com/repos/{full_name}/commits/{branch}", headers=headers, timeout=self.timeout)
                if ref.status_code in (401, 403, 404):
                    evidence.detail = "Repository metadata was reachable but the branch/commit source was inaccessible; CI truth remains UNKNOWN."
                    return RepositoryState(full_name=full_name, branch=branch, ci=TruthState.UNKNOWN, evidence=evidence)
                ref.raise_for_status()
                ref_payload = _json_object(ref, "GitHub commit")
                commit = ref_payload.get("sha")
                if commit is not None and not isinstance(commit, str):
                    raise ValueError("GitHub commit sha must be a string")
            if commit:
                ci, ci_detail = self._ci_state(full_name, commit, headers)
            evidence.detail = f"Live GitHub repository snapshot. {ci_detail}"
            return RepositoryState(full_name, branch, commit, ci, evidence)
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
            evidence.detail = f"GitHub source could not be refreshed safely: {type(exc).__name__}; CI truth remains UNKNOWN."
            return RepositoryState(full_name=full_name, ci=TruthState.UNKNOWN, evidence=evidence)

    def refresh_deployment(self, full_name: str) -> tuple[TruthState, Evidence, str | None]:
        """Read latest GitHub deployment/status without equating source availability with deployment health."""
        try:
            full_name = normalize_github_repository(full_name)
        except ValueError as exc:
            evidence = Evidence(source="github-deployments:invalid-repository", observed_at=utcnow(), freshness_seconds=600, kind="live_adapter", detail=f"Repository identifier rejected before GitHub deployment access: {exc}")
            return TruthState.UNKNOWN, evidence, None
        evidence = Evidence(source=f"github-deployments:{full_name}", observed_at=utcnow(), freshness_seconds=600, kind="live_adapter", url=f"https://github.com/{full_name}/deployments")
        headers = self._headers()
        try:
            response = requests.get(f"https://api.github.com/repos/{full_name}/deployments?per_page=1", headers=headers, timeout=self.timeout)
            if response.status_code in (401, 403, 404):
                evidence.detail = "GitHub deployment source is inaccessible; deployment truth remains UNKNOWN."
                return TruthState.UNKNOWN, evidence, None
            response.raise_for_status()
            deployments = _json_list(response, "GitHub deployments")
            if not deployments:
                evidence.detail = "No GitHub deployment exists; absence of a deployment is not deployment health."
                return TruthState.UNKNOWN, evidence, None
            if not isinstance(deployments[0], dict):
                raise ValueError("GitHub deployment item must be an object")
            deployment = deployments[0]
            deployment_id = deployment.get("id")
            environment = deployment.get("environment") or "unknown environment"
            deploy_sha = deployment.get("sha") or "unknown sha"
            if isinstance(deployment_id, bool) or not isinstance(deployment_id, int) or deployment_id <= 0:
                evidence.detail = f"Latest deployment for {environment} has an invalid deployment id; deployment truth remains UNKNOWN."
                return TruthState.UNKNOWN, evidence, None
            statuses = requests.get(f"https://api.github.com/repos/{full_name}/deployments/{deployment_id}/statuses?per_page=1", headers=headers, timeout=self.timeout)
            if statuses.status_code in (401, 403, 404):
                evidence.detail = f"Deployment {deployment_id} exists but its status source is inaccessible; deployment truth remains UNKNOWN."
                return TruthState.UNKNOWN, evidence, None
            statuses.raise_for_status()
            status_items = _json_list(statuses, "GitHub deployment statuses")
            if not status_items:
                evidence.detail = f"Deployment {deployment_id} ({environment}, {deploy_sha}) has no status evidence."
                return TruthState.UNKNOWN, evidence, None
            if not isinstance(status_items[0], dict):
                raise ValueError("GitHub deployment status item must be an object")
            status = status_items[0]
            state = status.get("state")
            raw_environment_url = status.get("environment_url") or deployment.get("environment_url")
            raw_target_url = status.get("target_url")
            environment_url = None
            rejected_environment_url = False
            if raw_environment_url:
                try:
                    environment_url = validate_public_http_url(raw_environment_url, resolve_dns=False)
                except UnsafeDestination:
                    rejected_environment_url = True
            safe_target_url = None
            if raw_target_url:
                try:
                    safe_target_url = validate_public_http_url(raw_target_url, resolve_dns=False)
                except UnsafeDestination:
                    safe_target_url = None
            if environment_url:
                evidence.url = environment_url
            elif safe_target_url:
                evidence.url = safe_target_url
            detail_suffix = "; environment_url rejected by network policy" if rejected_environment_url else ""
            evidence.detail = f"GitHub deployment {deployment_id}; environment={environment}; sha={deploy_sha}; state={state or 'UNKNOWN'}{detail_suffix}."
            if state == "success":
                return TruthState.GREEN, evidence, environment_url
            if state in ("failure", "error"):
                return TruthState.DEGRADED, evidence, environment_url
            return TruthState.UNKNOWN, evidence, environment_url
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
            evidence.detail = f"GitHub deployment source could not be refreshed safely: {type(exc).__name__}; deployment truth remains UNKNOWN."
            return TruthState.UNKNOWN, evidence, None


class HealthAdapter:
    REDIRECT_CODES = {301, 302, 303, 307, 308}

    def refresh(self, url: str) -> tuple[TruthState, Evidence]:
        evidence = Evidence(source="health-check", observed_at=utcnow(), freshness_seconds=300, kind="live_adapter")
        try:
            current = validate_public_http_url(url)
            original_host = urlsplit(current).hostname or ""
            evidence.source = f"health:{current}"
            evidence.url = current
            for _ in range(4):
                response = requests.get(current, timeout=6, allow_redirects=False)
                if response.status_code not in self.REDIRECT_CODES:
                    break
                current = validated_redirect_target(current, response.headers.get("Location", ""), original_host=original_host)
                evidence.url = current
            else:
                evidence.detail = "Health check exceeded the authorized redirect limit."
                return TruthState.UNKNOWN, evidence
            if 200 <= response.status_code < 300:
                evidence.detail = f"HTTP {response.status_code}; transport green only, not business correctness."
                return TruthState.GREEN, evidence
            evidence.detail = f"HTTP {response.status_code}"
            return TruthState.DEGRADED, evidence
        except UnsafeDestination as exc:
            evidence.detail = f"Health destination rejected by network policy: {exc}"
            return TruthState.UNKNOWN, evidence
        except requests.RequestException as exc:
            evidence.detail = f"Health adapter failed: {type(exc).__name__}"
            return TruthState.DEGRADED, evidence
