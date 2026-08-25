"""Repository-local observability signal truth for ObraSignal.

This module is operational metadata, not a second product/domain truth and not a
release GO/NO-GO decision. It deliberately refuses to infer readiness from an
HTTP 200, a process being alive, or a missing signal.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CONTRACT_VERSION = "observability-signal-truth-v0"

COMPONENT_STATES = frozenset(
    {
        "HEALTHY",
        "DEGRADED",
        "UNAVAILABLE",
        "UNKNOWN",
        "STALE",
        "DISABLED",
        "NOT_CONFIGURED",
    }
)

OPERABILITY_STATES = frozenset({"FULL", "DEGRADED", "UNAVAILABLE", "UNKNOWN"})


@dataclass(frozen=True)
class ComponentSignal:
    """Bounded operational state for one component/dependency.

    ``critical`` means the component is required for the intended runtime
    capability represented by this snapshot. Optional dependencies remain
    visible but do not silently turn the whole service unavailable.
    """

    name: str
    state: str
    critical: bool
    source: str
    freshness: str = "UNKNOWN"

    def __post_init__(self):
        if not self.name or len(self.name) > 64:
            raise ValueError("component name must be non-empty and bounded")
        if self.state not in COMPONENT_STATES:
            raise ValueError(f"unsupported component state: {self.state}")
        if not self.source or len(self.source) > 128:
            raise ValueError("component source must be non-empty and bounded")


@dataclass(frozen=True)
class HealthEndpointContract:
    present: bool
    semantic: str
    unconditional_ok: bool
    db_evidence: bool
    worker_progress_evidence: bool
    render_health_check_consumer: bool
    findings: tuple[str, ...]


@dataclass(frozen=True)
class WorkerSignalContract:
    present: bool
    loop_present: bool
    progress_signal_present: bool
    failure_signal_present: bool
    findings: tuple[str, ...]


def _function_source_tree(source: str, function_name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node
    return None


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        fn = child.func
        if isinstance(fn, ast.Name):
            names.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            names.add(fn.attr)
    return names


def _contains_name_fragment(node: ast.AST, fragments: Iterable[str]) -> bool:
    wanted = tuple(fragments)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and any(part in child.id.lower() for part in wanted):
            return True
        if isinstance(child, ast.Attribute) and any(part in child.attr.lower() for part in wanted):
            return True
    return False


def _jsonify_has_unconditional_ok_true(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        fn = child.func
        is_jsonify = isinstance(fn, ast.Name) and fn.id == "jsonify"
        is_jsonify = is_jsonify or (isinstance(fn, ast.Attribute) and fn.attr == "jsonify")
        if not is_jsonify:
            continue
        for keyword in child.keywords:
            if keyword.arg == "ok" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                return True
    return False


def scan_health_endpoint(app_source: str, render_source: str = "") -> HealthEndpointContract:
    """Classify what ``/api/v1/health`` actually proves from repository code.

    The scanner intentionally has no path that infers FULL_READINESS. A richer
    endpoint requires an explicit reviewed contract rather than heuristic
    promotion by this scanner.
    """

    node = _function_source_tree(app_source, "health")
    if node is None:
        return HealthEndpointContract(
            present=False,
            semantic="UNKNOWN",
            unconditional_ok=False,
            db_evidence=False,
            worker_progress_evidence=False,
            render_health_check_consumer="healthCheckPath: /api/v1/health" in render_source,
            findings=("HEALTH_ENDPOINT_MISSING",),
        )

    calls = _call_names(node)
    unconditional_ok = _jsonify_has_unconditional_ok_true(node)
    db_evidence = bool({"db", "execute"} & calls) or _contains_name_fragment(node, ("database", "sqlite"))
    worker_evidence = _contains_name_fragment(
        node,
        ("last_progress", "last_success", "heartbeat", "worker_state", "worker_health"),
    )
    render_consumer = "healthCheckPath: /api/v1/health" in render_source

    findings: list[str] = []
    if unconditional_ok and not db_evidence and not worker_evidence:
        semantic = "PROCESS_ALIVE"
        findings.append("UNCONDITIONAL_OK_WITHOUT_READINESS_EVIDENCE")
        if render_consumer:
            findings.append("FALSE_READINESS_RISK")
    else:
        semantic = "UNKNOWN_CONTRACT"
        findings.append("HEALTH_SEMANTIC_REVIEW_REQUIRED")

    return HealthEndpointContract(
        present=True,
        semantic=semantic,
        unconditional_ok=unconditional_ok,
        db_evidence=db_evidence,
        worker_progress_evidence=worker_evidence,
        render_health_check_consumer=render_consumer,
        findings=tuple(findings),
    )


def scan_worker_contract(app_source: str) -> WorkerSignalContract:
    """Detect whether a background worker exposes progress/failure state.

    A loop existing is not useful-progress evidence. The scanner looks only for
    explicit bounded state names; log text is not treated as a heartbeat.
    """

    node = _function_source_tree(app_source, "worker")
    if node is None:
        return WorkerSignalContract(
            present=False,
            loop_present=False,
            progress_signal_present=False,
            failure_signal_present=False,
            findings=("WORKER_NOT_FOUND",),
        )

    loop_present = any(isinstance(child, (ast.For, ast.While)) for child in ast.walk(node))
    progress = _contains_name_fragment(
        node,
        ("last_progress", "last_success", "heartbeat", "worker_state", "worker_health"),
    )
    failure = _contains_name_fragment(node, ("last_failure", "last_error", "failure_state"))

    findings: list[str] = []
    if loop_present and not progress:
        findings.append("NO_PROGRESS_SIGNAL")
    if loop_present and not failure:
        findings.append("NO_FAILURE_STATE")
    return WorkerSignalContract(
        present=True,
        loop_present=loop_present,
        progress_signal_present=progress,
        failure_signal_present=failure,
        findings=tuple(findings),
    )


def build_operability_snapshot(signals: Iterable[ComponentSignal]) -> dict:
    """Aggregate component signal truth without producing release readiness.

    Critical UNKNOWN/STALE stays UNKNOWN. Critical UNAVAILABLE or DISABLED is
    unavailable for that intended runtime capability. Optional component
    failures remain explicit in ``components`` and ``unknowns`` but do not by
    themselves claim the core runtime unavailable.
    """

    components = list(signals)
    names = [item.name for item in components]
    if len(names) != len(set(names)):
        raise ValueError("duplicate component signal")

    critical = [item for item in components if item.critical]
    if not critical:
        overall = "UNKNOWN"
    elif any(item.state in {"UNAVAILABLE", "DISABLED"} for item in critical):
        overall = "UNAVAILABLE"
    elif any(item.state in {"UNKNOWN", "STALE", "NOT_CONFIGURED"} for item in critical):
        overall = "UNKNOWN"
    elif any(item.state == "DEGRADED" for item in critical):
        overall = "DEGRADED"
    elif all(item.state == "HEALTHY" for item in critical):
        overall = "FULL"
    else:
        overall = "UNKNOWN"

    if overall not in OPERABILITY_STATES:
        raise AssertionError("invalid operability aggregate")

    return {
        "contract_version": CONTRACT_VERSION,
        "overall": overall,
        "components": [asdict(item) for item in components],
        "unknowns": [item.name for item in components if item.state in {"UNKNOWN", "STALE"}],
    }


def current_repository_signal_report(repo_root: str | Path = ".") -> dict:
    """Return a secret-free, repository-only signal report for the current tree."""

    root = Path(repo_root)
    app_source = (root / "app.py").read_text(encoding="utf-8")
    render_source = (root / "render.yaml").read_text(encoding="utf-8")
    health = scan_health_endpoint(app_source, render_source)
    worker = scan_worker_contract(app_source)

    return {
        "contract_version": CONTRACT_VERSION,
        "health_endpoint": asdict(health),
        "worker": asdict(worker),
        "unowned_signal_gaps": {
            "db_readiness": "UNKNOWN",
            "dependency_aggregation": "UNKNOWN",
            "privacy_safe_correlation": "UNKNOWN",
            "alerting": "UNKNOWN",
        },
    }


if __name__ == "__main__":
    print(json.dumps(current_repository_signal_report(), sort_keys=True, separators=(",", ":")))
