from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from factory_cloud.capabilities import Capability


@dataclass(frozen=True)
class ExecutionRequest:
    app_id: str
    mode: str
    task: str
    source: str | None
    canonical_head: str | None
    resume_at: str
    execution_branch: str | None = None
    execution_head: str | None = None
    required_capabilities: tuple[str, ...] = ()

    @property
    def target_head(self) -> str | None:
        """Exact repository revision this execution is allowed to observe/mutate.

        `canonical_head` remains canonical source truth. `execution_head` may point to
        a separately verified non-canonical development candidate. Falling back to
        canonical keeps old jobs/configs fail-safe and backward compatible.
        """
        return self.execution_head or self.canonical_head

    @property
    def required_capability_set(self) -> frozenset[Capability]:
        return frozenset(Capability(value) for value in self.required_capabilities)


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    next_active: str = ""
    next_items: tuple[str, ...] = ()
    wait_items: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    resume_at: str = ""
    last_verified: str | None = None
    last_green: str | None = None
    execution_branch: str | None = None
    execution_head: str | None = None
    error: dict[str, Any] | None = None


class AppAdapter(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


class RepositorySafeAdapter:
    """Fail-closed default adapter for repository-safe applications.

    The persistent orchestrator owns dispatch/checkpointing, not GitHub or production
    authority. Concrete repository tooling must be injected by the host process.
    Until then this adapter returns a deterministic dispatch boundary rather than
    pretending repository work happened.
    """

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            status="WAIT",
            evidence={
                "dispatch_boundary": "repository_tooling_adapter_required",
                "source": request.source,
                "canonical_head": request.canonical_head,
                "execution_head": request.execution_head,
                "execution_branch": request.execution_branch,
                "required_capabilities": list(request.required_capabilities),
            },
            next_active=request.task,
            blockers=("repository_tooling_adapter_required",),
            resume_at=request.task,
        )


class ReadOnlySourceAdapter:
    """Adapter for applications whose canonical repository/source is unresolved."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            status="WAIT",
            evidence={
                "dispatch_boundary": "canonical_source_unresolved",
                "mode": request.mode,
                "source": request.source,
                "required_capabilities": list(request.required_capabilities),
            },
            next_active=request.task,
            blockers=("canonical_source_truth_required_before_repository_mutation",),
            resume_at=request.task,
        )


class AdapterRegistry:
    def __init__(self, overrides: dict[str, AppAdapter] | None = None):
        self._overrides = dict(overrides or {})

    def for_app(self, app_id: str, mode: str) -> AppAdapter:
        if app_id in self._overrides:
            return self._overrides[app_id]
        if mode == "repository_safe_execution":
            return RepositorySafeAdapter()
        if mode == "read_only_until_source_resolved":
            return ReadOnlySourceAdapter()
        raise ValueError(f"unsupported Factory Cloud mode: {mode}")
