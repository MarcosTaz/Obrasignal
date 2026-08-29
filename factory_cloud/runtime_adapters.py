from __future__ import annotations

from pathlib import Path
from typing import Any

from factory_cloud.adapters import AdapterRegistry
from factory_cloud.verification import VerifiedDispatchAdapter
from factory_cloud.work_queue import QueuedAppAdapter, open_app_queue


def build_runtime_adapters(registry: dict[str, Any], queue_dir: Path | str) -> AdapterRegistry:
    """Build the real repository-safe runtime adapters on physically private queues.

    Every enabled repository-safe app gets one queue SQLite below ``queue_dir/app_id``.
    GitHub-backed execution is wrapped in exact branch/head verification before a
    queue job can be created. Read-only/unresolved apps receive no override and
    therefore retain the orchestrator's fail-closed default adapter.
    """
    root = Path(queue_dir)
    overrides = {}
    for app in registry.get("applications", []):
        activation = app.get("activation") or {}
        canonical = app.get("source_truth") or {}
        if activation.get("enabled") is not True or activation.get("mode") != "repository_safe_execution":
            continue

        app_id = str(app["app_id"])
        delegate = QueuedAppAdapter(open_app_queue(root, app_id))
        execution = app.get("execution_source") or {}
        repository = str(execution.get("repository") or canonical.get("repository") or "")
        branch = str(execution.get("branch") or canonical.get("canonical_branch") or "")
        expected_head = execution.get("head") or canonical.get("canonical_head")
        provider = execution.get("provider") or canonical.get("provider")
        if provider == "github":
            delegate = VerifiedDispatchAdapter(
                delegate,
                repository=repository,
                branch=branch,
                expected_head=expected_head,
            )
        overrides[app_id] = delegate
    return AdapterRegistry(overrides)
