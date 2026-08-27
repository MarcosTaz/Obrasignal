from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from .models import Evidence, RepositoryState, TruthState


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class GitHubAdapter:
    """Read-only adapter. No credentials are ever exposed to the frontend."""

    def __init__(self, token: str | None = None, timeout: int = 8):
        self.token = token or os.getenv("FCC_GITHUB_TOKEN")
        self.timeout = timeout

    def refresh_repo(self, full_name: str) -> RepositoryState:
        evidence = Evidence(source=f"github:{full_name}", observed_at=utcnow(), freshness_seconds=3600, kind="live_adapter", url=f"https://github.com/{full_name}")
        if not self.token:
            evidence.detail = "FCC_GITHUB_TOKEN not configured; live GitHub truth is UNKNOWN."
            return RepositoryState(full_name=full_name, ci=TruthState.UNKNOWN, evidence=evidence)
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        try:
            repo = requests.get(f"https://api.github.com/repos/{full_name}", headers=headers, timeout=self.timeout)
            repo.raise_for_status()
            data = repo.json(); branch = data.get("default_branch"); commit = None
            if branch:
                ref = requests.get(f"https://api.github.com/repos/{full_name}/commits/{branch}", headers=headers, timeout=self.timeout)
                ref.raise_for_status(); commit = ref.json().get("sha")
            evidence.detail = "Live GitHub repository snapshot"
            return RepositoryState(full_name, branch, commit, TruthState.UNKNOWN, evidence)
        except requests.RequestException as exc:
            evidence.detail = f"GitHub adapter failed: {type(exc).__name__}"
            return RepositoryState(full_name=full_name, ci=TruthState.DEGRADED, evidence=evidence)


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
