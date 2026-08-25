"""Fail-closed CI gate attribution for Engineering Operations.

This module classifies whether an observed workflow result is actually required
for a candidate owner. It never changes domain truth or authorization.
"""

from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

ATTRIBUTION_STATES = (
    "REQUIRED",
    "INCIDENTALLY_TRIGGERED",
    "NOT_APPLICABLE",
    "REQUIRED_NOT_RUN",
    "NEEDS_RECHECK",
)
OWNER_GATE_STATES = ("OWNER_CURRENT_GREEN", "RED", "NEEDS_RECHECK")
TRIGGER_AWARENESS_STATES = (
    "AUTO_TRIGGER_EXPECTED",
    "AUTO_TRIGGER_FILTERED_LEGITIMATELY",
    "MANUAL_DISPATCH_AVAILABLE",
    "WORKFLOW_MISSING",
    "REQUIRED_NOT_RUN",
    "ATTRIBUTION_UNKNOWN",
)

OWNER_GATE_PATH_CONTRACTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "engineering_ops.py",
            "engineering_ops_github.py",
            "engineering_ops_gate_attribution.py",
            "engineering_ops_manifest.json",
            "tests/test_engineering_ops.py",
            "tests/test_engineering_ops_github.py",
            "tests/test_engineering_ops_gate_attribution.py",
            "docs/ENGINEERING_OPS_ORCHESTRATION.md",
            ".github/workflows/engineering-ops-drift.yml",
        ),
        ("Engineering Ops Drift", "ObraSignal Quality", "ObraSignal CodeQL"),
    ),
)


@dataclass(frozen=True)
class GateAttribution:
    workflow: str
    state: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _matches_any_path(changed_paths: Iterable[str], filters: Sequence[str]) -> bool:
    paths = tuple(str(path) for path in changed_paths)
    return any(fnmatch.fnmatch(path, pattern) for path in paths for pattern in filters)


def required_workflows_for_changed_paths(changed_paths: Iterable[str]) -> set[str]:
    paths = tuple(str(path) for path in changed_paths)
    required: set[str] = set()
    for surface_patterns, workflows in OWNER_GATE_PATH_CONTRACTS:
        if _matches_any_path(paths, surface_patterns):
            required.update(workflows)
    return required


def extract_pull_request_paths(workflow_text: str) -> tuple[str, ...] | None:
    lines = workflow_text.splitlines()
    in_pull_request = False
    pull_indent = -1
    in_paths = False
    paths_indent = -1
    found_paths_key = False
    values: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if stripped.startswith("pull_request:"):
            in_pull_request = True
            pull_indent = indent
            in_paths = False
            continue
        if in_pull_request and indent <= pull_indent and not stripped.startswith("pull_request:"):
            break
        if not in_pull_request:
            continue
        if stripped == "paths:":
            found_paths_key = True
            in_paths = True
            paths_indent = indent
            continue
        if in_paths:
            if indent <= paths_indent:
                in_paths = False
                continue
            if stripped.startswith("-"):
                value = stripped[1:].strip().strip("'\"")
                if value:
                    values.append(value)
            else:
                return ()
    if not found_paths_key:
        return None
    return tuple(values)


def workflow_has_manual_dispatch(workflow_text: str) -> bool:
    return any(line.strip().startswith("workflow_dispatch:") for line in workflow_text.splitlines())


def classify_gate_attribution(
    *,
    workflow: str,
    workflow_path: str | None,
    changed_paths: Iterable[str],
    explicit_required_workflows: Iterable[str] = (),
    candidate_workflow_paths: Iterable[str] = (),
    path_filters: Sequence[str] | None = None,
    run_trigger_pr: int | None = None,
    candidate_pr: int | None = None,
) -> GateAttribution:
    required = {str(name) for name in explicit_required_workflows}
    candidate_workflows = {str(path) for path in candidate_workflow_paths}

    if workflow in required:
        return GateAttribution(workflow, "REQUIRED", "explicit changed-surface gate contract")

    if (
        run_trigger_pr is not None
        and candidate_pr is not None
        and run_trigger_pr != candidate_pr
        and workflow_path
        and workflow_path not in candidate_workflows
    ):
        return GateAttribution(
            workflow,
            "INCIDENTALLY_TRIGGERED",
            "run belongs to another PR context and workflow is absent from candidate tree",
        )

    if required and workflow_path and workflow_path in candidate_workflows:
        return GateAttribution(
            workflow,
            "NOT_APPLICABLE",
            "workflow is outside explicit changed-surface owner gate contract",
        )

    if workflow_path and workflow_path in candidate_workflows:
        if path_filters is None:
            return GateAttribution(workflow, "REQUIRED", "workflow is present with unfiltered pull_request contract")
        if len(path_filters) == 0:
            return GateAttribution(workflow, "NEEDS_RECHECK", "workflow path filter contract could not be parsed safely")
        if not _matches_any_path(changed_paths, path_filters):
            return GateAttribution(workflow, "NOT_APPLICABLE", "candidate delta does not match workflow pull_request path filters")
        return GateAttribution(workflow, "REQUIRED", "candidate delta matches repository workflow trigger contract")

    return GateAttribution(workflow, "NEEDS_RECHECK", "insufficient repository evidence to attribute gate safely")


def complete_required_gates(*, required_workflows: Iterable[str], observed_gate_states: Mapping[str, str]) -> list[GateAttribution]:
    result: list[GateAttribution] = []
    for workflow in sorted({str(name) for name in required_workflows}):
        state = observed_gate_states.get(workflow)
        if state in {None, "NOT_RUN", "HISTORICAL"}:
            result.append(GateAttribution(workflow, "REQUIRED_NOT_RUN", "required gate has no exact-head completed execution"))
        else:
            result.append(GateAttribution(workflow, "REQUIRED", "required gate observed"))
    return result


def classify_trigger_awareness(
    *,
    attribution: str,
    gate_state: str,
    workflow_present: bool,
    path_filters: Sequence[str] | None,
    changed_paths: Iterable[str],
    manual_dispatch_available: bool,
) -> str:
    if attribution == "NEEDS_RECHECK":
        return "ATTRIBUTION_UNKNOWN"
    if not workflow_present:
        return "WORKFLOW_MISSING"
    if attribution == "NOT_APPLICABLE" and path_filters:
        if not _matches_any_path(changed_paths, path_filters):
            return "AUTO_TRIGGER_FILTERED_LEGITIMATELY"
    if attribution == "REQUIRED_NOT_RUN":
        return "REQUIRED_NOT_RUN"
    if attribution == "REQUIRED" and gate_state in {"PASS", "FAIL", "IN_PROGRESS"}:
        return "AUTO_TRIGGER_EXPECTED"
    if gate_state == "NOT_RUN" and manual_dispatch_available:
        return "MANUAL_DISPATCH_AVAILABLE"
    if manual_dispatch_available and attribution == "REQUIRED":
        return "MANUAL_DISPATCH_AVAILABLE"
    return "ATTRIBUTION_UNKNOWN"


def evaluate_owner_gate_state(gates: Iterable[Mapping[str, str]]) -> tuple[str, str]:
    saw_required = False
    for gate in gates:
        attribution = str(gate.get("attribution") or "NEEDS_RECHECK")
        gate_state = str(gate.get("gate_state") or "UNKNOWN")
        workflow = str(gate.get("workflow") or "UNKNOWN")
        if attribution in {"NEEDS_RECHECK", "REQUIRED_NOT_RUN"}:
            return "NEEDS_RECHECK", f"{workflow}: {attribution}"
        if attribution != "REQUIRED":
            continue
        saw_required = True
        if gate_state == "FAIL":
            return "RED", f"{workflow}: required gate failed"
        if gate_state != "PASS":
            return "NEEDS_RECHECK", f"{workflow}: required gate is {gate_state}"
    if not saw_required:
        return "NEEDS_RECHECK", "no required gate contract proven"
    return "OWNER_CURRENT_GREEN", "all required exact-head owner gates passed"
