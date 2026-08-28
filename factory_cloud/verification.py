from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from typing import Any, Callable

from factory_cloud.adapters import AppAdapter, ExecutionRequest, ExecutionResult
from factory_cloud.state_store import utc_now


@dataclass(frozen=True)
class SourceVerification:
    status: str
    verified_at: str | None
    expected_head: str | None
    observed_head: str | None
    evidence: dict[str, Any]
    blocker: str | None = None


class GitHubHeadVerifier:
    """Read-only exact branch-head verifier; credentials stay in process env."""

    def __init__(self, opener: Callable[..., Any] | None = None):
        self.opener = opener or urllib.request.urlopen

    def verify(self, repository: str, branch: str, expected_head: str | None) -> SourceVerification:
        if not repository or not branch or not expected_head:
            return SourceVerification(
                "BLOCKED", None, expected_head, None,
                {"repository": repository, "branch": branch}, "canonical_source_truth_incomplete",
            )
        url = f"https://api.github.com/repos/{repository}/branches/{branch}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Factory-Cloud-Control-Plane"}
        token = os.getenv("FACTORY_CLOUD_GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self.opener(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            observed = str(((payload.get("commit") or {}).get("sha")) or "") or None
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return SourceVerification(
                "UNKNOWN", None, expected_head, None,
                {"repository": repository, "branch": branch, "error_type": type(exc).__name__},
                "source_verification_unavailable",
            )
        if observed != expected_head:
            return SourceVerification(
                "MISMATCH", utc_now(), expected_head, observed,
                {"repository": repository, "branch": branch}, "canonical_head_changed",
            )
        verified_at = utc_now()
        return SourceVerification(
            "VERIFIED", verified_at, expected_head, observed,
            {"repository": repository, "branch": branch, "head": observed}, None,
        )


class VerifiedDispatchAdapter:
    """Fail closed unless request and live exact execution source both match."""

    def __init__(
        self,
        delegate: AppAdapter,
        repository: str,
        branch: str,
        expected_head: str | None,
        verifier: GitHubHeadVerifier | None = None,
    ):
        self.delegate = delegate
        self.repository = repository
        self.branch = branch
        self.expected_head = expected_head
        self.verifier = verifier or GitHubHeadVerifier()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        request_branch = request.execution_branch or self.branch
        if (
            request.source != self.repository
            or request_branch != self.branch
            or request.target_head != self.expected_head
        ):
            return ExecutionResult(
                status="WAIT",
                evidence={
                    "source_verification": "REQUEST_MISMATCH",
                    "repository": self.repository,
                    "branch": self.branch,
                    "expected_head": self.expected_head,
                    "request_source": request.source,
                    "request_branch": request.execution_branch,
                    "request_target_head": request.target_head,
                    "canonical_head": request.canonical_head,
                },
                next_active=request.task,
                blockers=("execution_source_request_mismatch",),
                resume_at=request.task,
            )

        verification = self.verifier.verify(self.repository, self.branch, self.expected_head)
        if verification.status != "VERIFIED":
            return ExecutionResult(
                status="WAIT",
                evidence={
                    "source_verification": verification.status,
                    "verification_scope": "execution_source",
                    "expected_head": verification.expected_head,
                    "observed_head": verification.observed_head,
                    **verification.evidence,
                },
                next_active=request.task,
                blockers=(verification.blocker or "source_verification_required",),
                resume_at=request.task,
                last_verified=verification.verified_at,
            )
        result = self.delegate.execute(request)
        return replace(result, last_verified=verification.verified_at or result.last_verified)
